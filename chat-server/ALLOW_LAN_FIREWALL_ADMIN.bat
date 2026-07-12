@echo off
echo This must be run as Administrator.
netsh advfirewall firewall add rule name="ThorGor HoN Chat TCP 11031" dir=in action=allow protocol=TCP localport=11031 profile=private
pause
