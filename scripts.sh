nnvim() {
	nvim ~/.config/nvim/init.vim
}

## Edits .zshrc

nzsh() {
	nvim ~/.zshrc
}

## Edits .scripts.sh

nscript() {
	nvim ~/.scripts.sh
}

## Edits snippets 

ntsnip() {
	nvim ~/.config/nvim/UltiSnips/tex.snippets
}

nrsnip() {
	nvim ~/.config/nvim/UltiSnips/nroff.snippets
}

ncsnip() {
	nvim ~/.config/nvim/UltiSnips/cpp.snippets
}

nn() {
	nvim
}

ncod(){
	echo "Inserisci nome file: " 
	read nome
	if [[ $nome == "x" ]]; then 
		break
	fi
	mkdir ~/Documents/Università/III\ anno/Informatica/codice/$nome
	touch ~/Documents/Università/III\ anno/Informatica/codice/$nome/main.cpp
	cd ~/Documents/Università/III\ anno/Informatica/codice/$nome
	nvim ~/Documents/Università/III\ anno/Informatica/codice/$nome/main.cpp
}

## Compilazione g++

c() {
    if [[ -z "$1" ]]; then
        echo "Usage: c <file_sorgente>"
        return 1
    fi

    nome_sorgente="${1%.*}"

    g++ -std=c++20 -o "$nome_sorgente" "$1"

    if [[ $? -eq 0 ]]; then
        "./$nome_sorgente"
    else
        echo "Errore durante la compilazione di $1"
    fi
}

## Fisica

f3() {
	nvim ~/Documents/Note/Fisica/Fisica\ 3/appunti/master.tex
}

m() {
	nvim ~/Documents/Note/Fisica/Meccanica\ Quantistica/master.tex
}

## Matematica

a() {
	nvim ~/Documents/Note/Matematica/Analisi\ 2/master.tex
}

to() {
	nvim ~/Documents/Note/Matematica/Topologia/master.tex
}

ag() {
	nvim ~/Documents/Note/Matematica/Algebra/master.tex
}
## Display

dpon() {
	xrandr --output DP-1 --primary --mode 3840x2160 --rate 60.00 --output eDP-1 --mode 1920x1080 --rate 60.00 --below DP-1
	setxkbmap -option caps:swapescape,compose:ralt &
}

dpdockon() {
	xrandr --output DP-1 --primary --mode 3840x2160 --rate 60.00 --output eDP-1 --off
	nitrogen --restore &
	setxkbmap -option caps:swapescape,compose:ralt &
}

dpoff() {
	xrandr --output DP-1 --off --output eDP-1 --primary --mode 1920x1080 --rate 60.00
	nitrogen --restore &
}

## DWM

ninit(){
	nvim ~/.xinitrc
}

nsl(){
	cd ~/suckless/slstatus/
	nvim config.def.h
}

nlock(){
	cd ~/suckless/slock/
	nvim config.def.h
}

ndwm(){
	cd ~/suckless/dwm/
	nvim config.def.h
}

nst(){
	cd ~/suckless/st/
	nvim config.def.h
}

nmenu(){
	cd ~/suckless/dmenu/
	nvim config.def.h
}

comp(){
	sudo cp config.def.h config.h
	sudo make clean install
}

## Bluetooth
bton() {
	sudo systemctl enable --now bluetooth
}

btoff() {
	sudo systemctl disable --now bluetooth
}

cson() {
	bluetoothctl connect $casse
}

csoff() {
	bluetoothctl disconnect $casse
}

airon() {
	bluetoothctl connect $airpods
}

airoff() {
	bluetoothctl disconnect $airpods
}

## Nav
rnote() {
	ranger ~/Documents/Note
}

cnote() {
	cd ~/Documents/Note
}

cbin() {
	cd ~/.local/bin/	
}

## Dunst commands
dr() {
	pkill dunst
	dunst &
}

## Groff compiling

ge() {
	#preconv master.ms | eqn -Tpdf | groff -ms -Tpdf > master.pdf 
	groff -k -e master.ms -ms -Tpdf > master.pdf
	zathura master.pdf
}

gc() {
	groff -k -ms master.ms -Tpdf > master.pdf
	zathura master.pdf
}
