#!/bin/bash

# For the skids by a skid(?) lol


echo "
 @@@@@@   @@@  @@@  @@@  @@@@@@@         @@@@@@   @@@  @@@ 
@@@@@@@   @@@  @@@  @@@  @@@@@@@@       @@@@@@@   @@@  @@@ 
!@@       @@!  !@@  @@!  @@!  @@@       !@@       @@!  @@@ 
!@!       !@!  @!!  !@!  !@!  @!@       !@!       !@!  @!@ 
!!@@!!    @!@@!@!   !!@  @!@  !@!       !!@@!!    @!@!@!@! 
 !!@!!!   !!@!!!    !!!  !@!  !!!        !!@!!!   !!!@!!!! 
     !:!  !!: :!!   !!:  !!:  !!!            !:!  !!:  !!! 
    !:!   :!:  !:!  :!:  :!:  !:!  :!:      !:!   :!:  !:! 
:::: ::    ::  :::   ::   :::: ::  :::  :::: ::   ::   ::: 
:: : :     :   :::  :    :: :  :   :::  :: : :     :   : : 

                                      
                                         -- @debxrshi
"

# usage

if [ "$#" -eq 0 ] || [ -z "$1" ]
then
    echo "usage: skid.sh target.com"
    exit 1
else
    target=$1
fi

if [ -n "$target" ]
then
    echo -e "...Executing tools...\n"

# initial probing

    echo "[+] Probing target with httpx"

    httpx -u "$target" -fr -sc -title -td -server -retries 3 -fc 404 -lc -t 500 

# subfinder

    echo -e "\n[+] Hunting subdomains with subfinder \n\n"
    subfinder -d "$target" -o "${target}_subs"

# probing subs

    echo -e "\n Probing subdomains with httpx\n\n"
    httpx -l "${target}_subs" -fr -sc -title -td -server -retries 3 -fc 404 -lc -t 500 -o "${target}_subs_httpx"

# dnsx

# katana

# uro

# xsstrike

# dalfox 

fi
