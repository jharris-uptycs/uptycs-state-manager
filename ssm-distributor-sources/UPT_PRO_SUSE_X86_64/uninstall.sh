#!/usr/bin/env bash

version=$(sudo rpm -qa 2>/dev/null | grep uptycs)
sudo rpm -e $version