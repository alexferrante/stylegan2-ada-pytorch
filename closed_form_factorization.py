import argparse
import torch
import dnnlib
import legacy
import pickle

import numpy as np
from sklearn.decomposition import TruncatedSVD

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract factor/eigenvectors of latent spaces using closed form factorization"
    )
    parser.add_argument(
        "--out", type=str, default="factor.pt", help="name of the result factor file"
    )
    parser.add_argument("--ckpt", type=str, help="name of the model checkpoint")
    args = parser.parse_args()

    device = torch.device('cuda')
    with dnnlib.util.open_url(args.ckpt) as f:
        G = pickle.load(f)['G_ema'].to(device) # type: ignore

    modulate = {
        k[0]: k[1]
        for k in G.named_parameters()
        if "affine" in k[0] and "torgb" not in k[0] and "weight" in k[0] or ("torgb" in k[0] and "b4" in k[0] and "weight" in k[0] and "affine" in k[0])
    }

    weight_mat = []
    for k, v in modulate.items():
        weight_mat.append(v)

    W = torch.cat(weight_mat, 0)
    svds = torch.linalg.svd(W).V.to("cpu")

    # weight = W.cpu().clone().numpy()

    # Check the explained variance of SVD and PCA decompositions of the weight space
    # svd = TruncatedSVD(n_components=500, random_state=0)
    # res = svd.fit_transform(weight)
    # V = svd.components_
    # S = svd.singular_values_ 
    # print(svd.explained_variance_ratio_)

    # pca = IncrementalPCA(n_components=500, batch_size=1000)
    # res = pca.fit_transform(weight)
    # print(pca.explained_variance_ratio_)

    alt_weight_mat = []
    for k, v in modulate.items():
        w = v.cpu().detach().numpy()
        alt_weight_mat.append(w.T)

    alt_W = np.concatenate(alt_weight_mat, axis=1).astype(np.float32)
    alt_W = alt_W / np.linalg.norm(alt_W, axis=0, keepdims=True)
    eigvals, eigvecs = np.linalg.eig(alt_W.dot(alt_W.T))

    torch.save({"ckpt": args.ckpt, "eigvec": eigvecs.T, "eigval": eigvals, "svds": svds}, args.out)
