"Vim-plug
call plug#begin('~/.config/nvim/plugged')

"Plug 'itchyny/lightline.vim'

Plug 'lervag/vimtex'

Plug 'sirver/ultisnips'

"Plug 'catppuccin/nvim', { 'as': 'catppuccin' }

"
"
"Plug 'KeitaNakamura/tex-conceal.vim'

Plug 'arcticicestudio/nord-vim'

"Plug 'andreasvc/vim-256noir'

call plug#end()

" Ultisnips config
    let g:UltiSnipsExpandTrigger = '<tab>'
    let g:UltiSnipsJumpForwardTrigger = '<tab>'
    let g:UltiSnipsJumpBackwardTrigger = '<s-tab>'

"Vimtex config
    let g:tex_flavor='latex'
    let g:vimtex_view_method='zathura'
    let g:vimtex_quickfix_mode=0
" Tex-conceal
"    set conceallevel=1
"    let g:tex_conceal='abdmg'
"    hi Conceal ctermbg=none

" Autosave
autocmd TextChanged,TextChangedI *
    \ if &buftype ==# '' || &buftype == 'acwrite' |
    \     silent write |
    \ endif

" Numbers on the side    
set number relativenumber

" Syntax
syntax enable

" Catppuccin theme
"colorscheme catppuccin-frappe " catppuccin-latte, catppuccin-frappe, catppuccin-macchiato, catppuccin-mocha



"Nord Theme installation
colorscheme nord
let g:lightline = {
      \ 'colorscheme': 'nord',
\ }

" 256_noir Theme installation
" colorscheme 256_noir

" Nord Theme installation 
"colorscheme nord

" Change highlighting of cursor line when entering/leaving Insert Mode
set cursorline
highlight CursorLine cterm=NONE ctermfg=NONE ctermbg=233 guifg=NONE guibg=#121212
autocmd InsertEnter * highlight CursorLine cterm=NONE ctermfg=NONE ctermbg=234 guifg=NONE guibg=#1c1c1c
autocmd InsertLeave * highlight CursorLine cterm=NONE ctermfg=NONE ctermbg=233 guifg=NONE guibg=#121212



" Vim correction
setlocal spell
set spelllang=en_us
set spelllang+=it
inoremap <C-l> <C-g>u<Esc>[s1z=gi<C-g>u

" Opens a new terminal tab
nnoremap tt :term<cr>

" Exit from terminal mode through Exit
tnoremap <Esc> <C-\><C-n>

" Opens a new tab
nnoremap te :tabnew<cr>

" Navigating tabs
nnoremap tn :tabn<cr>
 
" Splitting a tab 
nnoremap ts :tab split<cr>

" Saving documents shortcut
nnoremap ww :ws<cr>

" Quitting the document
nnoremap qq :q<cr>

" Quitting the document without saving
nnoremap qf :q!<cr>


" Setting 256 colors
set t_Co=256
set t_AB=^[[48;5;%dm
set t_AF=^[[38;5;%dm


" Copying to clipboard
set clipboard=unnamedplus
