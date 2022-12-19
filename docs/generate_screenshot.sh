#!/bin/bash

cd "$(dirname "$0")"
termshot_exe="termshot"

if [ ! -f "$termshot_exe" ]
then
    echo "Download termshot from GitHub"
    wget https://github.com/homeport/termshot/releases/download/v0.2.5/termshot_0.2.5_linux_amd64.tar.gz
    tar -xzf termshot_0.2.5_linux_amd64.tar.gz termshot
fi

exe="conan-check-updates"
exe_win="${exe}.exe"

# use windows binary if avaiable (wsl)
if [ -x "$(command -v $exe_win)" ]; then
    echo "Windows executable found"
    exe=$exe_win
fi

echo "
[requires]
boost/1.79.0
catch2/3.2.0
fmt/9.0.0
nlohmann_json/3.10.0
" > conanfile.txt

./termshot --show-cmd --filename "screenshot.png" -- "$exe"
