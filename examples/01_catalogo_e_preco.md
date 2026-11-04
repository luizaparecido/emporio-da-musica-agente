# Catálogo e preço

**Objetivo:** Busca com filtro de preço, seguida de consulta a um produto específico com PIX e parcelamento.

Gerado por `scripts/generate_examples.py` com `gemini/gemini-3.5-flash-lite`. Data simulada: `2026-03-25T10:30-04:00`.

**Cliente:** Oi! Quais opções de violões disponíveis custando até R$1000?

> Tool `search_products`: `{"category": "Violões", "max_price": 1000}`

**Tom:** E aí! Tudo bem? Sou o Tom, assistente virtual da Empório da Música. 

Encontrei 12 modelos de violões de até R$ 1.000,00 por aqui. Vou te mostrar 8 opções bem legais para começar:

- Tagima Memphis AC-39 Nylon Natural: R$ 429,90
- Rozini RC-104 Nylon Estudante: R$ 459,90
- Shelby SN-100 Folk Aço Preto: R$ 549,00
- Giannini GF-1R Aço Folk Sunburst: R$ 579,90
- Yamaha C40 Nylon Natural: R$ 599,90
- Giannini GN-15 Nylon Cedr Natural: R$ 689,00
- Yamaha F310 Aço Natural: R$ 699,90
- Tagima Dallas Tuner Aço Natural: R$ 749,00

Se quiser, a gente pode dar uma filtrada por cordas de nylon ou aço, ou até por faixa de preço. Quer ver mais detalhes de algum deles?

**Cliente:** Prefiro de nylon. Tem algum bom para iniciante?

> Tool `search_products`: `{"max_price": 1000, "strings": "nylon", "category": "Violões"}`

**Tom:** Com certeza! O violão de nylon é ótimo para iniciantes porque machuca menos os dedos no começo. Dos 5 modelos disponíveis até R$ 1.000,00, estes aqui são super recomendados para quem está começando:

- Tagima Memphis AC-39 Nylon Natural: R$ 429,90
- Rozini RC-104 Nylon Estudante: R$ 459,90
- Yamaha C40 Nylon Natural: R$ 599,90
- Giannini GN-15 Nylon Cedr Natural: R$ 689,00
- Yamaha C70 Nylon Natural: R$ 849,00

O Yamaha C40 e o Rozini RC-104, por exemplo, são clássicos super buscados por quem está dando os primeiros passos. 

Quer saber mais sobre algum deles?

**Cliente:** E quanto custa o Takamine GD20? Dá pra parcelar?

> Tool `get_product_quote`: `{"name": "Takamine GD20"}`

**Tom:** O Takamine GD20 (modelo Takamine GD20 Dreadnought Natural) custa R$ 2.199,00. À vista no PIX sai por R$ 2.089,05 e dá para parcelar em até 12x de R$ 183,25 sem juros! 

É um violão de aço incrível, com tampo sólido em cedro e um timbre muito quente. 

Precisa de ajuda com mais alguma coisa?
