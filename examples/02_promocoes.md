# Promoção ativa e promoção vencida

**Objetivo:** Promoção não acumula com PIX (§6.2), e promoção encerrada é informada com transparência (§7.3).

Gerado por `scripts/generate_examples.py` com `gemini/gemini-3.5-flash-lite`. Data simulada: `2026-03-25T10:30-04:00`.

**Cliente:** Vocês têm ukulele em promoção?

> Tool `search_products`: `{"on_promotion": true, "category": "Ukuleles"}`

**Tom:** Temos sim! Olha só os ukuleles que estão em promoção por aqui:

- **Kalani KAL-700T Tenor Natural**
  De R$ 359,00 por R$ 323,10 (10% de desconto)

- **Ohana CK-20 Concert Natural**
  De R$ 549,00 por R$ 439,20 (20% de desconto)

Quer saber mais detalhes de algum deles ou precisa de ajuda para escolher?

**Cliente:** Quanto fica o Ohana CK-20? Se eu pagar no PIX tem mais 5% em cima?

> Tool `get_product_quote`: `{"name": "Ohana CK-20 Concert Natural"}`

**Tom:** O Ohana CK-20 está por R$ 439,20 (ele já está com 20% de desconto sobre o preço original de R$ 549,00). 

Como ele já está em promoção, o desconto de 5% no PIX não se acumula, mas você pode parcelar em até 5x de R$ 87,84 sem juros, se preferir! Precisa de mais alguma informação sobre ele?

**Cliente:** E o Crafter CE-15, ainda está com o desconto da Black Friday?

> Tool `list_promotions`: `{"name": "Black Friday"}`

**Tom:** A promoção de Black Friday já acabou, então o Crafter CE-15 Elétrico Nylon Natural está com o preço atual de R$ 3.899,00. 

Se quiser, posso te passar os detalhes de pagamento dele ou te mostrar outras opções! Precisa de mais alguma coisa?
