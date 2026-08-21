# Palavras que indicam que não é o produto puro (kits, acessórios, PCs completos)
# REMOVIDOS intencionalmente: 'suporte', 'cooler', 'ventoinha', 'base', 'case', 'gabinete'
# pois aparecem em descrições técnicas legítimas (ex: "sem cooler", "suporte a PCIe",
# "base clock") e 'gabinete'/'case' são categorias de produto válidas.
#
# [FIX Bug#1/#4] 'computador' e 'desktop' foram substituídos por frases específicas
# para evitar rejeitar descrições legítimas como "caixa de computador ATX" ou
# "processador de desktop Core i7".
#
# [FIX Bug#6] 'pc ' removido — era genérico demais e rejeitava gabinetes legítimos cujos
# títulos contêm "Capa para PC", "Capa PC" ou "PC Case" (descrição do tipo de produto).
# Substituído por frases específicas de PCs completos. Os demais casos (completo, kit, combo
# workstation, etc.) já cobrem os sistemas montados que precisam ser filtrados.
EXCLUSION_KEYWORDS = [
    'completo', 'combo', 'notebook', 'laptop',
    'workstation', 'all-in-one', 'torre', 'cpu completo',
    'bracket', 'shield', 'parafuso', 'adaptador', 'extensor', 'acessorio',
    # 'cabo' removido — PSUs frequentemente mencionam "com cabo 12V-2x6" no título Amazon,
    # causando falsos negativos. Acessórios de cabo puro são rejeitados pelo token matching.
    # 'kit' mantido intencionalmente — usuário seleciona UM pente de RAM por vez,
    # então kits de 2+ pentes (2x8GB, 2x16GB etc.) são inválidos para o caso de uso.
    # 'kit gamer/pc/computador' ficam como reforço para kits de PC completo.
    'kit', 'kit gamer', 'kit pc', 'kit computador',
    # [FIX Bug#8] 'desktop gamer' removido — bloqueava RAM com "Memória Desktop Gamer" no título
    # PCs completos já são cobertos por 'computador gamer', 'pc gamer', 'desktop completo' etc.
    # Frases específicas para PCs completos (substituem 'pc ' e os genéricos 'computador'/'desktop')
    'mini pc', 'barebone pc',
    'pc gamer', 'pc completo', 'pc montado', 'pc computador',
    'pc intel', 'pc amd', 'pc core', 'pc ryzen',
    'computador completo', 'computador gamer', 'computador montado',
    'computador intel', 'computador amd', 'computador core', 'computador ryzen',
    'desktop completo', 'desktop montado',
    'desktop intel', 'desktop amd', 'desktop core', 'desktop ryzen',
    # [FIX/MONITORING 15/08] Variantes com a ordem das palavras invertida em relação às
    # frases acima (ex: "ORIGIN PC Neuron Gaming PC" em vez de "PC Gamer"). Vistas em
    # produção deixando passar PCs completos de boutique (Origin PC, iBUYPOWER etc.) que
    # citam o modelo do componente no título. Cobre só os padrões observados até agora —
    # não é uma solução geral para ordem de palavras arbitrária, então pode continuar
    # havendo variações que escapem (ex: "Computador Gaming", "PC para Jogos").
    'gaming pc', 'gaming desktop', 'gaming computer',
]

# Sufixos que indicam PRODUTO DIFERENTE (não podem aparecer se não estão no modelo buscado)
VARIANT_SUFFIXES = [
    'xt', 'ti', 'super', 'kf', 'f', 'ultra', 'max', 'pro',
    'plus', 'boost', 'overclocked', 'turbo', 'extreme', 'premium',
    'x3d', '3d', 's', 'g', 'x',  # 'x' adicionado para cobrir 7600X, 5800X, etc.
    'i',  # 'i' para distinguir HX1200 de HX1200i (versão com monitoramento digital iCUE)
]

# Palavras genéricas que podem aparecer sem problema (são apenas marketing/descrição)
# [FIX] 'lpx' removido — NÃO é palavra genérica, é o nome de uma linha real de produto
# (Corsair Vengeance LPX vs Corsair Vengeance normal são pentes diferentes). Com 'lpx'
# na lista, uma busca por "Vengeance LPX" aceitava qualquer "Vengeance" sem LPX como
# se fosse o mesmo produto.
GENERIC_WORDS = [
    'radeon', 'geforce', 'ryzen', 'core', 'intel', 'amd', 'nvidia',
    'processador', 'processor', 'cpu', 'gpu', 'ssd', 'hdd', 'memoria',
    'memory', 'ram', 'placa', 'video', 'mae', 'motherboard', 'fonte',
    'power', 'supply', 'psu', 'gaming', 'oc', 'edition', 'overclock',
    'series', 'tri', 'dual', 'fan', 'fans', 'ventilador', 'refrigeracao',
    'western', 'digital', 'kingston', 'corsair', 'crucial', 'samsung',
    'seagate', 'wd', 'xpg', 'adata', 'sandisk', 'gskill', 'msi',
    'asus', 'gigabyte', 'asrock', 'evga', 'nzxt', 'fractal', 'design',
    'cooler', 'master', 'rise', 'mode', 'com', 'with', 'de', 'da', 'do',
    'para', 'e', 'and', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for',
    'black', 'white', 'rgb', 'argb', 'led', 'custom', 'windforce', 'phantom',
    'strix', 'tuf', 'rog', 'aorus', 'ventus', 'eagle', 'armor', 'twin', 'frozr',
    'nitro', 'pulse', 'red', 'devil', 'v2', 'v1', 'ex', 'lx',
    'preto', 'preta', 'branco', 'branca', 'sem', 'ate', 'max', 'turbo',
    'cache', 'nucleos', 'nucleo', 'geracao', 'interno', 'interna',
    'chipset', 'socket', 'suporte', 'compativel', 'alta', 'alto',
    'velocidade', 'leitura', 'gravacao', 'desempenho', 'gamer',
    'cooler', 'ventoinha', 'base', 'gabinete', 'case', 'torre'
]

# [FIX Bug#5] Fabricantes de chip — seus produtos são vendidos por terceiros
# (ASUS, MSI, Gigabyte, ZOTAC, etc.), então o nome da marca quase nunca aparece
# no título do produto. Pular brand check para esses fabricantes.
CHIP_MANUFACTURERS = {'nvidia', 'amd', 'intel'}

# [FIX] Safelist de capacidades reais de SSD/HD em GB, usada só para aceitar anúncios que
# escrevem a capacidade sem o "B" final (ex: "SA400S37/480G"). Sem essa safelist, aceitar
# qualquer número seguido de "G" bagunçaria com sufixos de modelo de CPU/GPU que também
# terminam em G (ex: Ryzen "5700G", "8700G") e não têm nada a ver com armazenamento.
KNOWN_STORAGE_CAPACITIES_GB = {
    120, 128, 240, 250, 256, 480, 500, 512, 960, 1000, 1024,
    2000, 2048, 4000, 4096, 8000, 8192
}

# [FIX/MONITORING 15/08] Safelist equivalente para capacidades de VRAM de GPU, usada só
# quando category == 'GPU'. Motivo de existir separada da safelist de storage acima: títulos
# de GPU às vezes escrevem a VRAM sem o "B" final (ex: "GeForce RTX 5050 WINDFORCE OC V2 8G"),
# e os valores típicos de VRAM (4, 6, 8, 10, 12, 16...) não têm nenhuma sobreposição
# significativa com a safelist de storage — usar a mesma lista simplesmente não teria o "8"
# nela (list pensada pra SSD/HD) e rejeitava o produto certo por falso negativo de capacidade.
KNOWN_VRAM_CAPACITIES_GB = {1, 2, 3, 4, 6, 8, 10, 11, 12, 16, 20, 24, 32, 48}
