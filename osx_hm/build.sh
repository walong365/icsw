#!/bin/sh

VERSION="0.0.1"

mkdir build
mkdir build/icsw-host-monitoring-$VERSION
mkdir build/icsw-host-monitoring-$VERSION/opt

cp -r ../initat ./build/icsw-host-monitoring-$VERSION
cp -r ../opt/cluster ./build/icsw-host-monitoring-$VERSION/opt
cp -r ./build/icsw-host-monitoring-$VERSION/opt/cluster/etc/cstores.d/client_sample_config.xml ./build/icsw-host-monitoring-$VERSION/opt/cluster/etc/cstores.d/client_config.xml
cp -r ./setup_template ./build/icsw-host-monitoring-$VERSION/setup.py

sed -i "s/VERSION_PLACEHOLDER/\"$VERSION\"/" ./build/icsw-host-monitoring-$VERSION/setup.py

tar -czpf ./build/icsw-host-monitoring-$VERSION.tar.gz -C ./build icsw-host-monitoring-$VERSION

SHA256SUM="$(shasum -a256 ./build/icsw-host-monitoring-$VERSION.tar.gz | head -c 64)"

cp icsw-host-monitoring_template.rb ./build/icsw-host-monitoring.rb

sed -i '' "s/URL_PLACEHOLDER/\"http:\/\/192.168.1.178\/icsw\/static\/icsw-host-monitoring-$VERSION.tar.gz\"/" ./build/icsw-host-monitoring.rb
sed -i '' '"s/VERSION_PLACEHOLDER/\"$VERSION\"/" ./build/icsw-host-monitoring.rb
sed -i '' '"s/SHA256_PLACEHOLDER/\"$SHA256SUM\"/" ./build/icsw-host-monitoring.rb
