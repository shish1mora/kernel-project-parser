#!/bin/bash

#Скрипт находится в проекте по пути /red-cvedb/
cd ~

# Клонирование репозитория
git clone https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git
cd linux
git remote add stable git://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable.git
git remote add history https://github.com/bootlin/linux-history.git
git fetch history --tags
git fetch stable --tags
git pull

# Создание ramdisk
mkdir /tmp/ramdisk
mount -t ramfs ramfs /tmp/ramdisk
chmod 777 /tmp/ramdisk

# Копирование исходников в ramdisk
cd ~
cp -r ~/linux /tmp/ramdisk

# Поднимаем docker по docker-compose файлу
cd ~/datamart-backend
docker-compose up -d

# Запуск парсера
cd ~/red-cvedb/modules
python kern_makedb_end.py
