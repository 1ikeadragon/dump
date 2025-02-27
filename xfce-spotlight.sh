#!/bin/bash

country=US
locale=en-US
imgPath=$HOME/.bingspotlight-xfce/
deleteImagesAfterNumDays=3
setDesktop=yes
setLockscreen=yes
setDM=no

mkdir -p ${imgPath}

dateTime=$(env TZ=UTC date +'%Y-%m-%dT%H:%M:%SZ')

json=$(curl "https://fd.api.iris.microsoft.com/v4/api/selection"\
    -G\
    -A ''\
    --data-urlencode "bcnt=1"\
    --data-urlencode "country=${country}"\
    --data-urlencode "fmt=json"\
    --data-urlencode "locale=${locale}"\
    --data-urlencode "placement=88000820"\
    2>/dev/null |
        jq -c '
            .batchrsp.items[].item |
            fromjson |
            .ad |
            {
                description: .description,
                entityId: .entityId,
                landscapeImageAsset: .landscapeImage.asset,
                portraitImageAsset: .portraitImage.asset,
                title: .title,
            }
        '
)

if [ -z "$json" ]; then
    echo "Failed to retrieve image data"
    exit 1
fi

IFS=$'\t' read -r description entity_id image_url portrait_image_asset title\
    <<<"$(<<<"${json}" jq -r '[ .description, .entityId, .landscapeImageAsset, .portraitImageAsset, .title ] | @tsv')"

imgName=${imgPath}/${entity_id}.jpeg
jsonPath=${imgPath}/${entity_id}.json

curl -s "$image_url" -o ${imgName}

echo "$json" > "$jsonPath"

if [ "$setDesktop" = "yes" ]; then
    if [ "$XDG_CURRENT_DESKTOP" = "XFCE" ]; then
        monitors=$(xfconf-query -c xfce4-desktop -l | grep last-image | cut -d/ -f2 | sort -u)
        
        for monitor in $monitors; do
            properties=$(xfconf-query -c xfce4-desktop -l | grep $monitor | grep last-image)
            for property in $properties; do
                xfconf-query -c xfce4-desktop -p $property -s "${imgName}"
            done
        done
    elif [ "$XDG_CURRENT_DESKTOP" = "GNOME" ]; then
        gsettings set org.gnome.desktop.background picture-uri "file://${imgName}"
        gsettings set org.gnome.desktop.background picture-uri-dark "file://${imgName}"
    elif [ "$XDG_CURRENT_DESKTOP" = "KDE" ]; then
        qdbus org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "
            desktops().forEach((d) => {
                d.currentConfigGroup = [
                    'Wallpaper',
                    'org.kde.image',
                    'General',
                ]
                d.writeConfig('Image', 'file://${imgName}')
                d.reloadConfig()
            })
        "
    fi
fi

if [ "$setLockscreen" = "yes" ]; then
    if [ -f "/usr/bin/light-locker" ]; then
        cp "${imgName}" "$HOME/.config/light-locker-background.jpg" 2>/dev/null
    fi
    
    if [ "$XDG_CURRENT_DESKTOP" = "GNOME" ]; then
        gsettings set org.gnome.desktop.screensaver picture-uri "file://${imgName}"
    fi
    
    if [ "$XDG_CURRENT_DESKTOP" = "KDE" ]; then
        kwriteconfig5 --file kscreenlockerrc --group Greeter --group Wallpaper --group org.kde.image --group General --key Image "file://${imgName}"
    fi
fi

if [ "$setDM" = "yes" ]; then
    if [ -f "/etc/lightdm/lightdm-gtk-greeter.conf" ]; then
        sudo cp "${imgName}" /usr/share/backgrounds/spotlight-wallpaper.jpeg 2>/dev/null
        sudo sed -i 's|^background=.*|background=/usr/share/backgrounds/spotlight-wallpaper.jpeg|' /etc/lightdm/lightdm-gtk-greeter.conf 2>/dev/null
    fi
fi
notify-send -a 'Spotlight Wallpaper' "$title" "$description"

if [ ${deleteImagesAfterNumDays} -gt 0 ]; then
    find ${imgPath} -type f -name "*.jpeg" -mtime +${deleteImagesAfterNumDays} -delete
    find ${imgPath} -type f -name "*.json" -mtime +${deleteImagesAfterNumDays} -delete
fi
