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
catch2/3.1.0
fmt/8.0.0
spdlog/1.9.0

[build_requires]
cmake/[>=3.20]

[generators]
cmake
" > conanfile.txt

./termshot --show-cmd --filename "screenshot.png" -- "$exe"
