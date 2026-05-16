import fitz
import os
from pathlib import Path

divergentes = [
    ("link_490.0_EWERTON_AUGUSTO_KOSTKA_-_Despesas_realizadas_no_m_cec6418951ee.pdf", 490.0, 45),
    ("link_150.0_AFRANIO_DA_SILVA_FIGUEIREDO_-_Despesas_realizadas_61150035d9bd.pdf", 150.0, 45),
    ("link_1.8_MATEUS_LACERDA_-_Despesas_realizadas_no_m_s_10_2024_15ab6fe62493.pdf", 1.8, 45),
    ("link_62.04_LUCIANA_GON_ALVES_REZENDE_-_Despesas_realizadas_n_7d97b703cd27.pdf", 62.04, 45),
    ("link_4939.4_JULIANA_MARTINS_PEREIRA_PASSOS_10179862669_-_Ins_ee97e8ed92fd.pdf", 4939.4, 22),
    ("link_3904.68_VILLAGE_ADMINISTRA_O_E_SERVI_OS_EIRELI_2025_287_93d931aba7e0.pdf", 3904.68, 22),
    ("link_2536.5_MGPRAG_CONTROLE_DE_PRAGAS_URBANAS_LTDA_-_Dedetiz_d170dd17faa0.pdf", 2536.5, 14),
    ("link_4176.96_CONSERVADORA_ATUANTE_LTDA_-_12_2025_52_100ea9184977.pdf", 4176.96, 12),
]

docs_dir = Path("documentos_nf")
imgs_dir = Path("divergentes_imgs")
imgs_dir.mkdir(exist_ok=True)

for pdf_nome, valor, score in divergentes:
    pdf_path = docs_dir / pdf_nome
    if pdf_path.exists():
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            img_nome = imgs_dir / f"{pdf_nome.replace('.pdf', '')}_p{i+1}.png"
            pix.save(img_nome)
            print(f"Salvo: {img_nome}")
        doc.close()
    else:
        print(f"NÃO ENCONTRADO: {pdf_path}")

print(f"\nImagens salvas em: {imgs_dir}")
