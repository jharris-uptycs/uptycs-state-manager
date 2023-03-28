#!/bin/bash
#
# Distributor package installer - Ubuntu based distros
#
filename=assets-uptycs-protect-5.7.0.25-Uptycs.deb

Install() {
  dpkg -i $filename
}

Install $filename