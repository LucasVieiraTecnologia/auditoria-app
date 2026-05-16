from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

pwa_dir = Path('pwa')
sizes = [192, 512]

for size in sizes:
    # Criar imagem com gradiente azul
    img = Image.new('RGB', (size, size), color=(37, 99, 235))
    draw = ImageDraw.Draw(img)
    
    # Adicionar gradiente simples
    for y in range(size):
        r = int(37 + (29 - 37) * y / size)
        g = int(99 + (78 - 99) * y / size)
        b = int(235 + (216 - 235) * y / size)
        draw.line([(0, y), (size, y)], fill=(r, g, b))
    
    # Círculo dourado no topo
    circle_r = size // 8
    circle_y = size // 5
    draw.ellipse(
        [(size//2 - circle_r, circle_y - circle_r), 
         (size//2 + circle_r, circle_y + circle_r)],
        fill=(251, 191, 36)
    )
    
    # Letra A branca
    try:
        font = ImageFont.truetype("arial.ttf", size//2)
    except:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size//2)
        except:
            font = ImageFont.load_default()
    
    text = "A"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2
    y = (size - text_height) // 2 + size//6
    
    draw.text((x, y), text, fill=(255, 255, 255), font=font)
    
    # Salvar ícones
    img.save(pwa_dir / f'icon-{size}.png')
    img.save(pwa_dir / f'icon-maskable-{size}.png')
    
    print(f"Icon {size}x{size} created successfully")

print("\nAll PWA icons created!")
