# Devolução e garantia (situação não trivial)

**Objetivo:** Verificação de identidade, seguida da aplicação das políticas de devolução com prazos calculados.

Gerado por `scripts/generate_examples.py` com `gemini/gemini-3.5-flash-lite`. Data simulada: `2026-03-25T10:30-04:00`.

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

**Tom:** Olá! Tudo bem? Sou o Tom, assistente virtual da Empório da Música. Com certeza, posso te ajudar a entender sobre a devolução.

Para eu verificar o seu caso, por favor, me informe o número do pedido e o seu telefone ou e-mail cadastrado na compra.

**Cliente:** É o pedido 7, comprei pelo site. Meu telefone é (67) 90000-0000.

> Tool `check_return_eligibility`: `{"reason": "arrependimento", "contact": "(67) 90000-0000", "order_id": 7}`

**Tom:** Não consegui confirmar os dados com essas informações. Poderia conferir se o número do pedido e o telefone estão certinhos, por favor?

**Cliente:** Foi mal, digitei errado. O certo é (67) 99789-0123.

> Tool `check_return_eligibility`: `{"order_id": 7, "reason": "arrependimento", "contact": "(67) 99789-0123"}`

**Tom:** Letícia, olhando aqui pelo sistema, o prazo de 7 dias corridos para devolução por arrependimento (contado a partir da previsão de entrega) era até 24/02/2026, então acabou passando dessa data.

Como eu não processo a devolução por aqui, se você quiser conversar com a equipe sobre o seu caso, posso abrir um chamado para eles avaliarem. Quer que eu abra?

**Cliente:** Poxa. E se o ukulele estiver com defeito de fabricação?

> Tool `check_return_eligibility`: `{"contact": "(67) 99789-0123", "order_id": 7, "reason": "defeito"}`

**Tom:** Para defeito de fabricação, Letícia, o prazo de 30 dias para troca direta encerrou em 05/03/2026 (contado da data da compra). Porém, a garantia legal de 90 dias ainda está válida até aproximadamente 18/05/2026 (contada a partir da previsão de entrega). 

Vale lembrar que a garantia não cobre mau uso ou desgaste natural, e a loja pode te ajudar intermediando com o fabricante. 

Quer que eu abra um ticket para a nossa equipe te orientar sobre como acionar a garantia?
