Firstly make sure you've got a functioning Pi camera module (test it with
`raspistill` to be certain). Then make sure you've got the following packages
installed:

    $ sudo apt-get install ffmpeg git python3-picamera python3-ws4py python3-rpi.gpio
 
Next, clone this repository:

    $ git clone https://github.com/waveform80/pistreaming.git

## Usage

Run the Python server script which should print out a load of stuff
to the console as it starts up:

    $ cd pistreaming
    $ python3 server.py


```
cat > /etc/init.d/microscope << EOF
#!/bin/bash
 
### BEGIN INIT INFO
# Provides:          microscope
# Required-Start:    $all
# Required-Stop:     
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Wifi microscope
### END INIT INFO

startDaemon() {
      cd /home/pi/microscope
      /usr/bin/python3 server.py > /var/log/microscope.log &
}

stopDaemon() {
    pkill -9 python3 &> /dev/null
}

restartDaemon() {
    stopDaemon
    startDaemon
}

case "$1" in
    start)
        startDaemon
        ;;
    stop)
        stopDaemon
        ;;
    restart)
        restartDaemon
        ;;
    status)
        ;;
    *)
        startDaemon
esac
exit 0
EOF
```


```
chmod 755 /etc/init.d/microscope
update-rc.d microscope defaults
```
