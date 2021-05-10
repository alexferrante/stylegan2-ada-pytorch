import os
import re
import subprocess
import argparse
import torch
from torchvision import utils # assumes you use torchvision 0.8.2; if you use the latest version, see comments below
import legacy
import dnnlib
from typing import List
import numpy as np
import random

"""
Simplification of apply_factor.py for my use-case
"""

#############################################################################################

def generate_images(z, label, truncation_psi, noise_mode, direction, file_name):
    img1 = G(z, label, truncation_psi=truncation_psi, noise_mode=noise_mode)
    img2 = G(z + direction, label, truncation_psi=truncation_psi, noise_mode=noise_mode)
    img3 = G(z - direction, label, truncation_psi=truncation_psi, noise_mode=noise_mode)
    return torch.cat([img3, img1, img2], 0)

def generate_image(z, label, truncation_psi, noise_mode):
    img = G(z, label, truncation_psi=truncation_psi, noise_mode=noise_mode)
    return img

def line_interpolate(zs, steps):
   out = []
   for i in range(len(zs)-1):
    for index in range(steps):
     fraction = index/float(steps) 
     out.append(zs[i+1]*fraction + zs[i]*(1-fraction))
   return out

def num_range(s: str) -> List[int]:
    '''Accept either a comma separated list of numbers 'a,b,c', a range 'a-c' and return as a list of ints or a string with "r{number}".'''
    if "r" in s:
        index = s.index("r")
        return int(s[index+1:])
    range_re = re.compile(r'^(\d+)-(\d+)$')
    m = range_re.match(s)
    if m:
        return list(range(int(m.group(1)), int(m.group(2))+1))
    vals = s.split(',')
    return [int(x) for x in vals]

#############################################################################################

if __name__ == "__main__":
    torch.set_grad_enabled(False)
    parser = argparse.ArgumentParser(description="Apply closed form factorization")
    parser.add_argument("-i", "--index", type=num_range, default="-1", help="index of eigenvector")
    parser.add_argument("--seeds", type=num_range, default="r1", help="list of random seeds or 'r10' for 10 random samples" )
    parser.add_argument(
        "-d",
        "--degree",
        type=float,
        default=5,
        help="scalar factors for moving latent vectors along eigenvector",
    )
    parser.add_argument("--output", type=str, default="/cff_output/", help="directory for result samples",)
    parser.add_argument("--ckpt", type=str, required=True, help="stylegan2-ada-pytorch checkpoints")
    parser.add_argument("--truncation", type=float, default=1, help="truncation factor")
    parser.add_argument("--mode", type=str, default="svds", choices=["svds", "eigvec"], help="source of latent vectors")
    parser.add_argument("factor", type=str, help="name of the closed form factorization result factor file")

    args = parser.parse_args()

    device = torch.device('cuda')
    if mode == 'svds':
        vec = torch.load(args.factor)[args.mode].to(device)
    elif mode == 'eigvec':
        vec_np = torch.load(args.factor)[args.mode]
        vec = torch.from_numpy(vec_np).to(device)
    index = args.index
    seeds = args.seeds

    with dnnlib.util.open_url(args.ckpt) as f:
        G = legacy.load_network_pkl(f)['G_ema'].to(device)

    if not os.path.exists(args.output):
      os.makedirs(args.output)

    label = torch.zeros([1, G.c_dim], device=device)
    noise_mode = "const" # default
    truncation_psi = args.truncation

    latents = []
    mode = "random"
    log_str = ""

    index_list_of_eigenvalues = []

    if isinstance(seeds, int):
        for i in range(seeds):
            latents.append(random.randint(0,2**32-1)) # 2**32-1 is the highest seed value
        mode = "random"
        log_str = str(seeds) + " samples"
    else:
        latents = seeds
        mode = "seeds"
        log_str = str(seeds)

    print(f"""
    Checkpoint: {args.ckpt}
    Factor: {args.factor}
    Outpur Directory: {args.output}
    Mode: {mode} ({log_str})
    Index: eigenvectors {index}
    Truncation: {truncation_psi}
    """)

    for l in latents:
        print(f"Generate images for seed ", l)

        z = torch.from_numpy(np.random.RandomState(l).randn(1, G.z_dim)).to(device)

        file_name = ""
        image_grid_vec = []

        if len(index) ==  1 and index[0] == -1: # use all 
            index_list_of_eigenvalues = [*range(len(vec))]
            file_name = f"seed-{l}_index-all_degree-{args.degree}.png"
        else: # use certain indexes as eigenvalues
            index_list_of_eigenvalues = index
            str_index_list = '-'.join(str(x) for x in index)
            file_name = f"seed-{l}_index-{str_index_list}_degree-{args.degree}.png"

        for j in index_list_of_eigenvalues:
            current_vec = vec[:, j].unsqueeze(0)
            direction = args.degree * current_vec
            image_group = generate_images(z, label, truncation_psi, noise_mode, direction, file_name)
            image_grid_vec.append(image_group)

        print("Saving image ", os.path.join(args.output, file_name))
        grid = utils.save_image(
            torch.cat(image_grid_vec, 0),
            os.path.join(args.output, file_name),
            nrow = 3,
            normalize=True, 
            range=(-1, 1) # change range to value_range for latest torchvision
        )