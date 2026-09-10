import math
import shutil
from pathlib import Path
from PIL import Image, ImageFilter

IMAGES_DIR = Path(
    "/Users/johnpineda/Library/CloudStorage/GoogleDrive-engineeringwithjp@gmail.com/My Drive/NEDA Technologies/Clients/All Elite Construction/Projects/89 Hillside Ave, Bergenfield/After/Images"
)
BACKUP_DIR = IMAGES_DIR / "_original_unretouched_backup"
SCRATCH_DIR = Path("/Users/johnpineda/.gemini/antigravity/brain/d68f9e28-f459-483c-acb6-b659d86c53ab/scratch")

def backup_originals():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("*.jpg", "*.JPG", "*.png", "*.PNG"):
        for f in IMAGES_DIR.glob(ext):
            dest = BACKUP_DIR / f.name
            if not dest.exists():
                shutil.copy2(f, dest)
    print(f"Backed up originals to {BACKUP_DIR}")

def patch_horizontal(im, tgt_box, src_box):
    tx1, ty1, tx2, ty2 = tgt_box
    sx1, sy1, sx2, sy2 = src_box
    target_w = tx2 - tx1
    target_h = ty2 - ty1
    
    clean_patch = im.crop((sx1, sy1, sx2, sy2))
    tiled = Image.new('RGBA', (target_w, target_h))
    cur_x = 0
    flip = False
    while cur_x < target_w:
        p = clean_patch if not flip else clean_patch.transpose(Image.FLIP_LEFT_RIGHT)
        w_to_copy = min(p.width, target_w - cur_x)
        tiled.paste(p.crop((0, 0, w_to_copy, target_h)), (cur_x, 0))
        cur_x += w_to_copy
        flip = not flip
        
    mask = Image.new('L', (target_w, target_h), 255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=1.2))
    im.paste(tiled, (tx1, ty1), mask)
    return im

def patch_vertical(im, tgt_box, src_box):
    tx1, ty1, tx2, ty2 = tgt_box
    sx1, sy1, sx2, sy2 = src_box
    target_w = tx2 - tx1
    target_h = ty2 - ty1
    
    clean_patch = im.crop((sx1, sy1, sx2, sy2))
    tiled = Image.new('RGBA', (target_w, target_h))
    cur_y = 0
    flip = False
    while cur_y < target_h:
        p = clean_patch if not flip else clean_patch.transpose(Image.FLIP_TOP_BOTTOM)
        h_to_copy = min(p.height, target_h - cur_y)
        tiled.paste(p.crop((0, 0, target_w, h_to_copy)), (0, cur_y))
        cur_y += h_to_copy
        flip = not flip
        
    mask = Image.new('L', (target_w, target_h), 255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=1.2))
    im.paste(tiled, (tx1, ty1), mask)
    return im

def patch_horizontal_sloped(im, tx1, tx2, ty_func, src_box):
    target_w = tx2 - tx1
    sx1, sy1, sx2, sy2 = src_box
    target_h = sy2 - sy1
    clean_patch = im.crop((sx1, sy1, sx2, sy2))
    
    tiled = Image.new('RGBA', (target_w, target_h))
    cur_x = 0
    flip = False
    while cur_x < target_w:
        p = clean_patch if not flip else clean_patch.transpose(Image.FLIP_LEFT_RIGHT)
        w_copy = min(p.width, target_w - cur_x)
        tiled.paste(p.crop((0, 0, w_copy, target_h)), (cur_x, 0))
        cur_x += w_copy
        flip = not flip
        
    mask = Image.new('L', (target_w, target_h), 255).filter(ImageFilter.GaussianBlur(radius=1.5))
    
    for x in range(tx1, tx2):
        col_x = x - tx1
        ty = int(ty_func(x))
        for dy in range(target_h):
            alpha = mask.getpixel((col_x, dy)) / 255.0
            if alpha > 0:
                p_tile = tiled.getpixel((col_x, dy))
                p_orig = im.getpixel((x, ty + dy))
                blended = tuple(int(p_tile[i] * alpha + p_orig[i] * (1 - alpha)) for i in range(3))
                im.putpixel((x, ty + dy), blended)
    return im

def repair_all_photos():
    backup_originals()
    
    # 1. DJI_0167.JPG (4K Top-Down Aerial)
    im167 = Image.open(BACKUP_DIR / "DJI_0167.JPG").convert("RGBA")
    clean_167 = im167.crop((2200, 1088, 2550, 1142))
    tiled_167 = Image.new("RGBA", (440, 54))
    tiled_167.paste(clean_167, (0, 0))
    tiled_167.paste(clean_167.transpose(Image.FLIP_LEFT_RIGHT), (clean_167.width, 0))
    mask_167 = Image.new("L", (440, 54), 255).filter(ImageFilter.GaussianBlur(radius=1.5))
    im167.paste(tiled_167, (1755, 1088), mask_167)
    im167.convert("RGB").save(IMAGES_DIR / "DJI_0167.JPG", quality=98)
    print("Repaired DJI_0167.JPG")
    
    # 2. DJI_0168.JPG (4K Front Aerial)
    im168 = Image.open(BACKUP_DIR / "DJI_0168.JPG").convert("RGB")
    ty_func_168 = lambda x: 723 - (x - 1798) * (4.0 / (2315.0 - 1798.0))
    patch_horizontal_sloped(im168, 1798, 2315, ty_func_168, (2318, 719, 2680, 764))
    im168.save(IMAGES_DIR / "DJI_0168.JPG", quality=98)
    print("Repaired DJI_0168.JPG")
    
    # 3. DJI_0166.JPG (4K Diagonal Perspective)
    im166 = Image.open(BACKUP_DIR / "DJI_0166.JPG").convert("RGBA")
    crop_box_166 = (2050, 680, 2750, 1100)
    strip_166 = im166.crop(crop_box_166)
    angle_166 = math.degrees(math.atan(0.50))
    rotated_166 = strip_166.rotate(angle_166, expand=True, resample=Image.BICUBIC)
    
    tgt_box_rot = (82, 324, 432, 385)
    src_box_rot = (434, 324, 690, 385)
    tw_166 = tgt_box_rot[2] - tgt_box_rot[0]
    th_166 = tgt_box_rot[3] - tgt_box_rot[1]
    
    clean_patch_166 = rotated_166.crop(src_box_rot)
    tiled_166 = Image.new('RGBA', (tw_166, th_166))
    cx = 0
    fl = False
    while cx < tw_166:
        p = clean_patch_166 if not fl else clean_patch_166.transpose(Image.FLIP_LEFT_RIGHT)
        wc = min(p.width, tw_166 - cx)
        tiled_166.paste(p.crop((0, 0, wc, th_166)), (cx, 0))
        cx += wc
        fl = not fl
        
    mask_rot_166 = Image.new('L', (tw_166, th_166), 255).filter(ImageFilter.GaussianBlur(radius=1.5))
    full_mask_rot = Image.new('L', rotated_166.size, 0)
    full_mask_rot.paste(mask_rot_166, (tgt_box_rot[0], tgt_box_rot[1]))
    rotated_166.paste(tiled_166, (tgt_box_rot[0], tgt_box_rot[1]), mask_rot_166)
    
    unrot_166 = rotated_166.rotate(-angle_166, expand=True, resample=Image.BICUBIC)
    unrot_mask_166 = full_mask_rot.rotate(-angle_166, expand=True, resample=Image.BICUBIC)
    dw = (unrot_166.width - strip_166.width) // 2
    dh = (unrot_166.height - strip_166.height) // 2
    final_strip = unrot_166.crop((dw, dh, dw + strip_166.width, dh + strip_166.height))
    final_mask = unrot_mask_166.crop((dw, dh, dw + strip_166.width, dh + strip_166.height))
    im166.paste(final_strip, (crop_box_166[0], crop_box_166[1]), final_mask)
    im166.convert("RGB").save(IMAGES_DIR / "DJI_0166.JPG", quality=98)
    print("Repaired DJI_0166.JPG")
    
    # 4-9: 1080p Drone Frames
    frames_1080p = [
        ('DJI_0159.jpg', (795, 368, 975, 395), (980, 368, 1115, 395), 'H'),
        ('DJI_0160.jpg', (803, 520, 905, 542), (907, 520, 995, 542), 'H'),
        ('DJI_0160_2.jpg', (845, 526, 937, 542), (938, 526, 984, 542), 'H'),
        ('DJI_0162.jpg', (940, 431, 1102, 451), (832, 431, 938, 451), 'H'),
        ('DJI_0162_1.jpg', (950, 400, 1102, 422), (842, 400, 948, 422), 'H'),
        ('DJI_0163.jpg', (962, 350, 992, 488), (965, 492, 995, 585), 'V'),
    ]
    for fname, tgt, src, orientation in frames_1080p:
        im = Image.open(BACKUP_DIR / fname).convert('RGBA')
        if orientation == 'H':
            patched = patch_horizontal(im, tgt, src)
        else:
            patched = patch_vertical(im, tgt, src)
        patched.convert('RGB').save(IMAGES_DIR / fname, quality=98)
        print(f"Repaired {fname}")

if __name__ == "__main__":
    repair_all_photos()
    print("All 9 Bergenfield roof photos successfully retouched!")
