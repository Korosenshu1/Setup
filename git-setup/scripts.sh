nnvim() {
	nvim ~/.config/nvim/init.vim
}

# Edits .zshrc

nzsh() {
	nvim ~/.zshrc
}

# Edits .scripts.sh
nscript() {
	nvim ~/.scripts.sh
}

# Edits tex.snippets 
ntsnip() {
	nvim ~/.config/nvim/UltiSnips/tex.snippets
}

ncsnip() {
	nvim ~/.config/nvim/UltiSnips/cpp.snippets
}

nn() {
	nvim
}

edp() {
	nvim ~/Files/Equazioni\ alle\ derivate\ parziali/appunti/master.tex
}

aedp() {
	cp ~/Files/Equazioni\ alle\ derivate\ parziali/appunti/master.pdf ~/Documents/Università/Appunti/Appunti\ di\ EDP.pdf
	cp -r ~/Files/Equazioni\ alle\ derivate\ parziali/appunti ~/Documents/Università/III\ anno/Equazioni\ alle\ derivate\ parziali/ 
}

am2() {
	nvim ~/Files/Analisi\ 2/appunti/master.tex
}

aam2() {
	cp ~/Files/Analisi\ 2/appunti/master.pdf ~/Documents/Università/Appunti/Appunti\ di\ Analisi\ 2/Appunti\ di\ Analisi\ 2.pdf
	cp -r ~/Files/Analisi\ 2/appunti ~/Documents/Università/II\ anno/Analisi\ 2/
}

ar() {
	nvim ~/Files/Analisi\ Reale/appunti/master.tex
}

aar() {
	cp ~/Files/Analisi\ Reale/appunti/master.pdf ~/Documents/Università/Appunti/Appunti\ di\ Analisi\ Reale.pdf
	cp -r ~/Files/Analisi\ Reale/appunti ~/Documents/Università/Matematica/Analisi\ Reale/
}


amc() {
	cp ~/Files/Meccanica\ Classica/appunti/master.pdf ~/Documents/Università/Appunti/Appunti\ di\ Meccanica\ Classica/Appunti\ di\ Meccanica\ Classica.pdf
	cp -r ~/Files/Meccanica\ Classica/appunti ~/Documents/Università/II\ anno/Meccanica\ Classica/ 
}

fis2() {
	nvim ~/Files/Fisica\ 2/appunti/master.tex
}


afis2() {
	cp ~/Files/Fisica\ 2/appunti/master.pdf ~/Documents/Università/Appunti/Appunti\ di\ Fisica\ 2.pdf
	cp -r ~/Files/Fisica\ 2/appunti ~/Documents/Università/II\ anno/Fisica\ 2/ 
}

mq() {
	nvim ~/Files/Meccanica\ Quantistica/appunti/master.tex
}

amq() {
	cp ~/Files/Meccanica\ Quantistica/appunti/master.pdf ~/Documents/Università/Appunti/Appunti\ di\ Meccanica\ Quantistica.pdf
	cp -r ~/Files/Meccanica\ Quantistica/appunti ~/Documents/Università/III\ anno/Meccanica\ Quantistica/ 
}

lab() {
	nvim ~/Files/Laboratorio\ 3/appunti/master.tex
}

alab() {
	cp ~/Files/Laboratorio\ 3/appunti/master.pdf ~/Documents/Università/Appunti/Appunti\ di\ Laboratorio\ 3.pdf
	cp -r ~/Files/Laboratorio\ 3/appunti ~/Documents/Università/III\ anno/Laboratorio\ 3
}

inf() {
	nvim ~/Files/Informatica/appunti/master.tex
}

ainf() {
	cp ~/Files/Informatica/appunti/master.pdf ~/Documents/Università/Appunti/Appunti\ di\ Informatica.pdf
	cp -r ~/Files/Informatica/appunti ~/Documents/Università/III\ anno/Informatica
}

met2() {
	nvim ~/Files/Metodi\ 2/appunti/master.tex
}

met2n() {
	nvim ~/Files/Metodi\ 2/note/master.tex
}

amet2(){
	cp ~/Files/Metodi\ 2/appunti/master.pdf ~/Documents/Università/Appunti/Appunti\ Metodi\ 2/Appunti\ di\ Metodi\ 2.pdf
	cp -r ~/Files/Metodi\ 2/appunti ~/Documents/Università/III\ anno/Metodi\ 2/ 
}

cod(){
	cd ~/Documents/Università/III\ anno/Informatica/codice
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

# Compilazione g++
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


#### Per il PC

ms() {
	nvim ~/Documents/Meccanica\ Statistica/master.tex
}

f3() {
	nvim ~/Documents/Fisica\ 3/appunti/master.tex
}

m() {
	nvim ~/Documents/Meccanica\ Quantistica/appunti/master.tex
}

fm() {
	nvim ~/Documents/Formulario\ MC/master.tex
}

ams() {
	cp ~/Documents/Meccanica\ Statistica/master.pdf ~/Desktop/Appunti\ di\ Meccanica\ Statistica.pdf
}

af3() {
	cp ~/Documents/Fisica\ 3/appunti/master.pdf ~/Desktop/Appunti\ di\ Fisica\ 3.pdf
}

am() {
	cp ~/Documents/Meccanica\ Quantistica/appunti/master.pdf ~/Desktop/Appunti\ di\ Meccanica\ Quantistica.pdf
}

afm() {
	cp ~/Documents/Formulario\ MC/master.pdf ~/Desktop/Formulario\ MC.pdf
}
