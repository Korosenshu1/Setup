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

## Edits tex.snippets 

ntsnip() {
	nvim ~/.config/nvim/UltiSnips/tex.snippets
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

af3() {
	cp ~/Documents/Note/Fisica/Fisica\ 3/appunti/master.pdf ~/Desktop/Appunti\ di\ Fisica\ 3.pdf
}

m() {
	nvim ~/Documents/Note/Fisica/Meccanica\ Quantistica/master.tex
}

am() {
	cp ~/Documents/Note/Fisica/Meccanica\ Quantistica/master.pdf ~/Desktop/Appunti\ di\ Meccanica\ Quantistica.pdf
}

s() {
	nvim ~/Documents/Note/Fisica/Struttura\ della\ Materia/master.tex
}

as() {
	cp ~/Documents/Note/Fisica/Struttura\ della\ Materia/master.pdf ~/Desktop/Appunti\ di\ Struttura\ della\ Materia.pdf
}

## Matematica

an() {
	nvim ~/Documents/Note/Matematica/Analisi\ 2/master.tex
}

aan() {
	cp ~/Documents/Note/Matematica/Analisi\ 2/master.pdf ~/Desktop/Note\ di\ Analisi\ 2.pdf
}

### Bluetooth

bt() {
	case "$1" in 
		on) 
			sudo systemctl enable --now bluetooth
			;;
		off) 
			sudo systemctl disable --now bluetooth
			;;
		*) 
			echo "Utilizzare comando on per abilitare e off per disabilitare."
			return 1
			;;
	esac
}
