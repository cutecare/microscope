Сперва необходимо подключить камеру к устройству и проверить, что она работоспособна настроив ее использование в raspi-config, перезагрузив и затем выполнив команду:

    $ raspistill -o test.jpg
    
Обновим систему:    

    $ sudo apt-get -y update && apt-get -y upgrade
    $ reboot

Теперь устанавливаем дополнительные компоненты, необходимые для работы веб-сервера:    

    $ sudo apt-get -y install ffmpeg git python3-picamera python3-ws4py python3-rpi.gpio dnsmasq hostapd
 
Клонируем репозиторий:

    $ cd /home/pi
    $ git clone https://github.com/cutecare/microscope.git

Регистрируем сервис, реализующий веб-сервер:

```
sudo -s
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

Регистрируем автоматический запуск сервиса при старте малинки:

```
chmod 755 /etc/init.d/microscope
update-rc.d microscope defaults
```

Настраиваем малинку для работы в режиме WiFi точки доступа, редактируем файл

    $ vi /etc/dhcpcd.conf

и добавляем в конце

```
interface wlan0
    static ip_address=192.168.2.1/24
    nohook wpa_supplicant
```

далее

    $ sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig  
    $ sudo vi /etc/dnsmasq.conf
    
добавляем в конец файла строки

```
interface=wlan0      
  dhcp-range=192.168.2.2,192.168.2.20,255.255.255.0,24h
```

Настраиваем точку доступа, открываем на редактирование

    $ sudo vi /etc/hostapd/hostapd.conf

и добавляем параметры нашей новой сети

```
interface=wlan0
driver=nl80211
ssid=Microscope
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=11111111
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
```

Теперь прописываем путь к этому конфигурационному файлу

    $ sudo vi /etc/default/hostapd
    
добавляем в конце

```
DAEMON_CONF="/etc/hostapd/hostapd.conf"
```

перезагружаем.

При помощи мобильного телефона или планшета ищем новую WiFi-сеть с названием Microscope, подключаемся указывая пароль 11111111 и в адресной строке браузера вводим http://192.168.2.1 после чего должно открыться приложение для управления микроскопом.

<img src="https://github.com/cutecare/microscope/blob/master/assets/IMG-20190126-WA0004.jpg?raw=true">
