# conciliacao-estoque

Concilia o estoque do ERP com os arquivos que três armazéns terceirizados mandam, lote a lote, e diz o que precisa de ação.

Os dados são fictícios (gerados por `gerar_dados.py`). O problema é de verdade: cada armazém manda o arquivo de um jeito (um usa `;` e vírgula decimal, outro conta em caixas, outro escreve o lote `l2610 - 3` em vez de `L2610-3`), e a diferença real fica escondida no meio da diferença de formato.

## Como roda

```bash
pip install -r requirements.txt
python gerar_dados.py
python main.py
python -m pytest -q
```

`main.py` gera `saida/conciliacao.csv` com um status por lote:

- `OK` / `DENTRO_TOLERANCIA` (até 1 un. ou 0,5%, configurável)
- `EM_TRANSITO`: a diferença é exatamente o que está em nota em trânsito
- `FALTA_NO_ARMAZEM` / `SOBRA_NO_ARMAZEM`: sobrou diferença sem explicação
- `SO_NO_ERP` / `SO_NO_ARMAZEM`

O gerador planta divergências conhecidas em `dados/gabarito.csv`, então dá para conferir o resultado em vez de confiar no olho. Na base padrão sai 22/22, sem alerta a mais.

## Notas

A chave é sku + depósito + lote. Conciliando só por SKU, um lote trocado passa batido porque o total bate.

Trânsito só explica a diferença se bater no valor exato. Um trânsito de 20 não justifica uma sobra de 30 (tem teste para isso).

Chave repetida ou SKU sem fator de caixa no cadastro param o processo com erro. Prefiro isso a um número errado sem aviso.

Se fosse para produção, eu guardaria o histórico diário: diferença que some sozinha em dois dias quase sempre é trânsito que ninguém lançou.
