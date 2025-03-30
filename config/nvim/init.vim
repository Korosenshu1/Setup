"Vim-plug
call plug#begin('~/.config/nvim/plugged')

"Plug 'itchyny/lightline.vim'

Plug 'lervag/vimtex'

Plug 'sirver/ultisnips'

" Plug 'arcticicestudio/nord-vim'

Plug 'ellisonleao/gruvbox.nvim'

call plug#end()

" Ultisnips config
    let g:UltiSnipsExpandTrigger = '<tab>'
    let g:UltiSnipsJumpForwardTrigger = '<tab>'
    let g:UltiSnipsJumpBackwardTrigger = '<s-tab>'

"Vimtex config
    let g:tex_flavor='latex'
    let g:vimtex_view_method='zathura'
    let g:vimtex_quickfix_mode=0

" Autosave
autocmd TextChanged,TextChangedI *
    \ if &buftype ==# '' || &buftype == 'acwrite' |
    \     silent write |
    \ endif

" Numbers on the side    
set number relativenumber

" Vim correction
setlocal spell
set spelllang=en_us
set spelllang+=it

" Col 
colorscheme gruvbox

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

" Quitting the document
nnoremap qq :q<cr>

" Quitting the document without saving
nnoremap qf :q!<cr>

" Setting 256 colors
set t_Co=256
set t_AB=^[[48;5;%dm
set t_AF=^[[38;5;%dm


" Copying and cutting to clipboard
nnoremap ,y "+y
vnoremap ,y "+y
nnoremap ,d "+d
vnoremap ,d "+d

" Remove background
hi Normal ctermbg=none guibg=none

" Neovide
let g:neovide_opacity = 0.6
let g:neovide_normal_opacity = 0.6
let g:neovide_scale_factor=1

" Compilazione groff
autocmd BufWritePost *.ms silent !groff -k -e -ms % -Tpdf > %:r.pdf &

" Apertura file pdf
nnoremap <leader>op :call OpenPDF()<CR>

function! OpenPDF()
  let l:pdf_file = expand('%:r') . ".pdf"
  let l:pdf_path = expand('%:p:h') . "/" . l:pdf_file
  if filereadable(l:pdf_path)
    execute "silent !zathura " . shellescape(l:pdf_path) . " &"
  else
    echo "PDF file not found: " . l:pdf_file
  endif
endfunction

" Rileva il filetype di file con estensione .ms
"augroup filetypedetect
"  autocmd!
"  autocmd BufRead,BufNewFile *.ms setfiletype nroff
"augroup END
