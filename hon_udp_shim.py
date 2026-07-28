import argparse
import binascii
import select
import socket
import time
from pathlib import Path


def now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def format_packet(data: bytes) -> str:
    hex_text = binascii.hexlify(data).decode("ascii")
    grouped = " ".join(hex_text[i:i + 2] for i in range(0, len(hex_text), 2))
    ascii_text = "".join(chr(b) if 32 <= b <= 126 else "." for b in data)
    return f"len={len(data)} hex={grouped} ascii={ascii_text}"


def classify_packet(data: bytes) -> str:
    if len(data) >= 4 and data[:3] == b"\x00\x00\x01":
        return f"cmd=0x{data[3]:02x}({chr(data[3]) if 32 <= data[3] <= 126 else '?'})"
    return "cmd=raw"


def extract_cpacket_strings(data: bytes) -> list[str]:
    chunks: list[str] = []
    current = bytearray()
    for byte in data:
        if byte == 0:
            if current:
                try:
                    text = current.decode("utf-8", errors="strict")
                except UnicodeDecodeError:
                    text = ""
                if text and all(31 < ord(ch) < 127 for ch in text):
                    chunks.append(text)
            current.clear()
        else:
            current.append(byte)
    return chunks


def describe_special_packet(data: bytes) -> str:
    if len(data) < 4 or data[:3] != b"\x00\x00\x01":
        return ""

    command = data[3]
    payload = data[4:]
    strings = extract_cpacket_strings(payload)

    if command == 0xC0:
        labels = [
            "product",
            "version",
            "username",
            "cookie",
            "ip",
            "acc_key",
            "acc_key_short_hash",
            "acc_key_hash",
        ]
        paired = []
        for label, value in zip(labels, strings):
            paired.append(f"{label}={value!r}")
        if len(strings) > len(labels):
            paired.extend(f"extra_{index}={value!r}" for index, value in enumerate(strings[len(labels):], start=1))
        return "CONNECT_C0 " + " ".join(paired)

    if command == 0x51 and strings:
        return "SERVER_Q1 " + " ".join(f"text_{index}={value!r}" for index, value in enumerate(strings, start=1))

    if command in {0xC3, 0xC9}:
        return f"CONTROL_{command:02X}"

    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="UDP shim/logger for HoN browser and server traffic.")
    parser.add_argument(
        "--preset",
        choices=["thorgor-public-list"],
        help="Apply a known-good local preset for ThorGor public-list experiments.",
    )
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, default=11236)
    parser.add_argument("--target-host", default="127.0.0.1")
    parser.add_argument("--target-port", type=int, default=11235)
    parser.add_argument("--log-file", default="work/hon_udp_shim.log")
    parser.add_argument("--idle-timeout", type=float, default=120.0)
    parser.add_argument(
        "--browser-reply-timeout",
        type=float,
        default=1.5,
        help="Seconds to wait before logging that a forwarded HoN browser probe received no server reply.",
    )
    parser.add_argument(
        "--answer-browser-o",
        action="store_true",
        help="Answer HoN browser 0xCA probes directly with a minimal synthetic 'o' reply.",
    )
    parser.add_argument(
        "--answer-browser-f",
        action="store_true",
        help="Answer HoN browser 0xCA probes directly with an experimental synthetic 'f' reply.",
    )
    parser.add_argument(
        "--answer-browser-both",
        action="store_true",
        help="Answer HoN browser 0xCA probes directly with synthetic 'o' and 'f' replies, in that order.",
    )
    parser.add_argument(
        "--no-forward-browser",
        action="store_true",
        help="Do not forward HoN browser 0xCA probes to the real server.",
    )
    parser.add_argument(
        "--browser-o-value",
        type=int,
        default=0,
        help="32-bit little-endian payload value for synthetic browser 'o' replies.",
    )
    parser.add_argument("--browser-name", default="Unnamed Server")
    parser.add_argument(
        "--browser-ip",
        default="client",
        help="IP string to return in the synthetic browser reply. Use 'client' to mirror the probing client address.",
    )
    parser.add_argument(
        "--browser-version",
        default="3.2.7",
        help="Version-like dotted triplet for the synthetic browser 'f' reply field the HoN client tokenizes.",
    )
    parser.add_argument("--browser-local-60c", default="")
    parser.add_argument("--browser-local-598", default="")
    parser.add_argument("--browser-map", default="caldavar")
    parser.add_argument("--browser-local-630", default="sandbox")
    parser.add_argument("--browser-local-5ec", default="normal")
    parser.add_argument("--browser-local-654", type=int, default=0)
    parser.add_argument("--browser-bvar2", type=int, default=0)
    parser.add_argument("--browser-local-55c", type=int, default=0)
    parser.add_argument("--browser-local-538", type=int, default=0)
    parser.add_argument("--browser-local-664", type=int, default=0)
    parser.add_argument("--browser-local-665", type=int, default=0)
    parser.add_argument("--browser-local-655", type=int, default=0)
    parser.add_argument("--browser-local-57c", type=int, default=0)
    parser.add_argument("--browser-local-660", type=int, default=0)
    parser.add_argument("--browser-local-558", type=int, default=10)
    parser.add_argument("--browser-local-5f0", type=int, default=0)
    parser.add_argument("--browser-local-65c", type=int, default=0)
    args = parser.parse_args()

    if args.preset == "thorgor-public-list":
        args.listen_port = 11236
        args.target_host = "127.0.0.1"
        args.target_port = 11235
        args.log_file = "work/hon_udp_shim_public_list.log"
        args.answer_browser_f = True
        args.answer_browser_o = False
        args.answer_browser_both = False
        args.no_forward_browser = True
        args.browser_name = "Unnamed Server"
        args.browser_ip = "127.0.0.1"
        args.browser_version = "3.2.7"
        args.browser_map = "caldavar"
        # Ghidra shows this field is effectively checked as empty-vs-nonempty mode state.
        # For the public browser path, try the empty variant first.
        args.browser_local_60c = ""
        args.browser_local_598 = "sandbox"
        args.browser_local_630 = "US"
        args.browser_local_5ec = "normal"
        args.browser_local_654 = 1
        args.browser_bvar2 = 1
        args.browser_local_558 = 10

    log_path = Path(args.log_file)
    if not log_path.is_absolute():
        log_path = Path(__file__).resolve().parent / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(line: str) -> None:
        text = f"{now_text()} | {line}"
        print(text, flush=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_sock.bind((args.listen_host, args.listen_port))
    client_sock.setblocking(False)

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.bind(("0.0.0.0", 0))
    server_sock.setblocking(False)

    target = (args.target_host, args.target_port)
    last_client = None
    last_activity = time.time()
    pending_browser_queries: dict[bytes, dict[str, object]] = {}

    log(
        f"LISTEN {args.listen_host}:{args.listen_port} -> TARGET {args.target_host}:{args.target_port} "
        f"(server-side local port {server_sock.getsockname()[1]})"
    )
    if args.preset:
        log(f"PRESET {args.preset}")
    if args.answer_browser_f or args.answer_browser_both:
        log(
            "BROWSER_F "
            f"name={args.browser_name!r} ip={args.browser_ip!r} local_60c={args.browser_local_60c!r} "
            f"version={args.browser_version!r} local_598={args.browser_local_598!r} "
            f"map={args.browser_map!r} local_630={args.browser_local_630!r} local_5ec={args.browser_local_5ec!r} "
            f"flags=654:{args.browser_local_654} b:{args.browser_bvar2} 55c:{args.browser_local_55c} "
            f"538:{args.browser_local_538} 664:{args.browser_local_664} 665:{args.browser_local_665} "
            f"655:{args.browser_local_655} 57c:{args.browser_local_57c} 660:{args.browser_local_660} "
            f"558:{args.browser_local_558} 5f0:{args.browser_local_5f0} 65c:{args.browser_local_65c}"
        )
    if args.answer_browser_o or args.answer_browser_both:
        log(f"BROWSER_O value={args.browser_o_value}")

    def encode_cpacket_wstring(text: str) -> bytes:
        return text.encode("utf-8") + b"\x00"

    def make_browser_o_reply(query: bytes) -> bytes | None:
        if len(query) != 6 or query[:3] != b"\x00\x00\x01" or query[3] != 0xCA:
            return None
        # Experimental browser reply:
        # prefix 00 00 01 + command 'o' + 32-bit payload.
        return b"\x00\x00\x01" + bytes([ord("o")]) + args.browser_o_value.to_bytes(4, "little", signed=True)

    def make_browser_f_reply(query: bytes, client_addr: tuple[str, int]) -> bytes | None:
        if len(query) != 6 or query[:3] != b"\x00\x00\x01" or query[3] != 0xCA:
            return None

        token = query[4:6]
        client_ip = client_addr[0] if args.browser_ip == "client" else args.browser_ip

        payload = bytearray()
        payload += token
        payload += encode_cpacket_wstring(args.browser_name)
        payload += bytes([args.browser_local_654 & 0xFF])
        payload += bytes([args.browser_bvar2 & 0xFF])
        payload += encode_cpacket_wstring(args.browser_local_60c)
        # Ghidra shows this field is tokenized into three numeric components on the client,
        # which fits a version triplet much better than an IP string.
        payload += encode_cpacket_wstring(args.browser_version)
        payload += bytes([args.browser_local_55c & 0xFF])
        payload += bytes([args.browser_local_538 & 0xFF])
        payload += bytes([args.browser_local_664 & 0xFF])
        payload += bytes([args.browser_local_665 & 0xFF])
        payload += encode_cpacket_wstring(args.browser_local_598)
        payload += encode_cpacket_wstring(args.browser_map)
        payload += encode_cpacket_wstring(args.browser_local_630)
        payload += encode_cpacket_wstring(args.browser_local_5ec)
        payload += bytes([args.browser_local_655 & 0xFF])
        payload += args.browser_local_57c.to_bytes(4, "little", signed=True)
        payload += bytes([args.browser_local_660 & 0xFF])
        payload += args.browser_local_558.to_bytes(2, "little", signed=False)
        payload += args.browser_local_5f0.to_bytes(2, "little", signed=False)
        payload += bytes([args.browser_local_65c & 0xFF])
        return b"\x00\x00\x01" + bytes([ord("f")]) + payload

    while True:
        ready, _, _ = select.select([client_sock, server_sock], [], [], 0.5)
        now = time.time()
        expired_tokens: list[bytes] = []
        for token, info in pending_browser_queries.items():
            sent_at = float(info["sent_at"])
            if now - sent_at >= args.browser_reply_timeout:
                addr = info["client_addr"]
                log(
                    "BROWSER_TIMEOUT "
                    f"token={token.hex()} client={addr[0]}:{addr[1]} "
                    f"target={args.target_host}:{args.target_port} waited={now - sent_at:.3f}s"
                )
                expired_tokens.append(token)
        for token in expired_tokens:
            pending_browser_queries.pop(token, None)
        if not ready:
            if time.time() - last_activity > args.idle_timeout:
                log("IDLE timeout reached; still listening.")
                last_activity = time.time()
            continue

        for sock_obj in ready:
            if sock_obj is client_sock:
                data, addr = client_sock.recvfrom(65535)
                last_client = addr
                last_activity = time.time()
                log(f"CLIENT_RX {addr[0]}:{addr[1]} | {classify_packet(data)} | {format_packet(data)}")
                special = describe_special_packet(data)
                if special:
                    log(f"CLIENT_RX_DETAIL {addr[0]}:{addr[1]} | {special}")
                browser_replies: list[tuple[str, bytes]] = []
                if args.answer_browser_both:
                    browser_o_reply = make_browser_o_reply(data)
                    if browser_o_reply is not None:
                        browser_replies.append(("synthetic_o", browser_o_reply))
                    browser_f_reply = make_browser_f_reply(data, addr)
                    if browser_f_reply is not None:
                        browser_replies.append(("synthetic_f", browser_f_reply))
                elif args.answer_browser_f:
                    browser_f_reply = make_browser_f_reply(data, addr)
                    if browser_f_reply is not None:
                        browser_replies.append(("synthetic_f", browser_f_reply))
                elif args.answer_browser_o:
                    browser_o_reply = make_browser_o_reply(data)
                    if browser_o_reply is not None:
                        browser_replies.append(("synthetic_o", browser_o_reply))
                is_browser_query = (
                    len(data) == 6 and data[:3] == b"\x00\x00\x01" and data[3] == 0xCA
                )
                for reply_kind, browser_reply in browser_replies:
                    sent = client_sock.sendto(browser_reply, addr)
                    log(f"CLIENT_TX {addr[0]}:{addr[1]} | {reply_kind}={sent} | {format_packet(browser_reply)}")
                if is_browser_query and args.no_forward_browser:
                    log("SERVER_TX skipped for browser query")
                    continue
                sent = server_sock.sendto(data, target)
                log(f"SERVER_TX {target[0]}:{target[1]} | forwarded={sent}")
                if is_browser_query:
                    token = data[4:6]
                    pending_browser_queries[token] = {
                        "sent_at": time.time(),
                        "client_addr": addr,
                        "query": data,
                    }
                    log(
                        "BROWSER_FORWARD "
                        f"token={token.hex()} client={addr[0]}:{addr[1]} "
                        f"target={target[0]}:{target[1]}"
                    )
            else:
                data, addr = server_sock.recvfrom(65535)
                last_activity = time.time()
                log(f"SERVER_RX {addr[0]}:{addr[1]} | {classify_packet(data)} | {format_packet(data)}")
                special = describe_special_packet(data)
                if special:
                    log(f"SERVER_RX_DETAIL {addr[0]}:{addr[1]} | {special}")
                if len(data) >= 6 and data[:3] == b"\x00\x00\x01":
                    token = data[4:6]
                    pending = pending_browser_queries.pop(token, None)
                    if pending is not None:
                        sent_at = float(pending["sent_at"])
                        client_addr = pending["client_addr"]
                        log(
                            "BROWSER_REPLY "
                            f"token={token.hex()} from={addr[0]}:{addr[1]} "
                            f"to={client_addr[0]}:{client_addr[1]} latency={time.time() - sent_at:.3f}s"
                        )
                if last_client is None:
                    log("CLIENT_TX skipped: no client seen yet")
                    continue
                sent = client_sock.sendto(data, last_client)
                log(f"CLIENT_TX {last_client[0]}:{last_client[1]} | forwarded={sent}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print(f"{now_text()} | STOP requested", flush=True)
        raise SystemExit(0)
