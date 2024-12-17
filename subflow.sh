#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: $0 <domain>"
  exit 1
fi

domain="$1"
output_file="${domain}_subdomains.txt"
temp_file="temp_${domain}.txt"
cleaned_file="${domain}_cleaned.txt"
alive_file="${domain}_alive.txt"
threads=50  

function run_subfinder_parallel() {
    input_file=$1
    output_file=$2
    echo "[*] Running subfinder on subdomains in parallel..."
    cat "$input_file" | xargs -P "$threads" -n 1 -I {} subfinder -d {} -all -silent -o - >> "$output_file"
}

echo "[*] Running subfinder on: $domain..."
subfinder -d "$domain" -all -recursive -silent -o "$output_file"

previous_count=0
current_count=$(wc -l < "$output_file")

echo "[*] Found $current_count subdomains. Checking recursively..."

while [ "$current_count" -gt "$previous_count" ]; do
    echo "[*] Running recursively with multi-threading on new subdomains..."
    previous_count=$current_count

    run_subfinder_parallel "$output_file" "$temp_file"

    
    sort -u "$output_file" "$temp_file" -o "$output_file"
    > "$temp_file"  

    current_count=$(wc -l < "$output_file")
    echo "[*] Total subdomains found so far: $current_count"
done

echo "[*] Cleaning up subdomains..."
awk -F'.' '
{
  subdomain=$0
  gsub("^www\\.", "", subdomain)
  if (!(subdomain in seen)) {
    seen[subdomain]=1
    print $0
  }
}' "$output_file" > "$cleaned_file"

echo "[*] Cleaned subdomains saved to: $cleaned_file"

echo "[*] Checking if subdomains are alive with $threads threads..."
httpx -l "$cleaned_file" -silent -o "$alive_file" -nc -t "$threads"

echo "[*] Alive subdomains saved to: $alive_file"

rm -f "$temp_file"

echo "[*] Recursive enumeration complete. Found $(wc -l < "$alive_file") alive subdomains."

rmm -f "$alive_file" -o subsmm

echo "[*] Generated mindmap file for $domain."
