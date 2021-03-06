#!/usr/bin/env python

import os.path as osp

import click
import fcn
import numpy as np
import skimage.io
import torch
from torch.autograd import Variable
import torchfcn
import tqdm


@click.command()
@click.argument('model_file', type=click.Path(exists=True))
@click.option('--deconv/--nodeconv', default=False)
def main(model_file, deconv):
    root = osp.expanduser('~/data/datasets')
    val_loader = torch.utils.data.DataLoader(
        torchfcn.datasets.VOC2011ClassSeg(
            root, split='seg11valid', transform=True),
        batch_size=1, shuffle=False,
        num_workers=4, pin_memory=True)

    n_class = len(val_loader.dataset.class_names)

    print('==> Loading model file: %s' % model_file)
    model = torchfcn.models.FCN32s(n_class=21, deconv=deconv)
    if torch.cuda.is_available():
        model = model.cuda()
    model_data = torch.load(model_file)
    try:
        model.load_state_dict(model_data)
    except Exception:
        model.load_state_dict(model_data['model_state_dict'])
    model.eval()

    print('==> Evaluating with VOC2011ClassSeg set11valid')
    visualizations = []
    metrics = []
    for batch_idx, (data, target) in tqdm.tqdm(enumerate(val_loader),
                                               total=len(val_loader),
                                               ncols=80, leave=False):
        if torch.cuda.is_available():
            data, target = data.cuda(), target.cuda()
        data, target = Variable(data, volatile=True), Variable(target)
        score = model(data)

        imgs = data.data.cpu()
        lbl_pred = score.data.max(1)[1].cpu().numpy()[:, 0, :, :]
        lbl_true = target.data.cpu()
        for img, lt, lp in zip(imgs, lbl_true, lbl_pred):
            img, lt = val_loader.dataset.untransform(img, lt)
            acc, acc_cls, mean_iu, fwavacc = \
                fcn.utils.label_accuracy_score(lt, lp, n_class=n_class)
            metrics.append((acc, acc_cls, mean_iu, fwavacc))
            if len(visualizations) < 9:
                viz = fcn.utils.visualize_segmentation(
                    lp, lt, img, n_class=n_class)
                visualizations.append(viz)
    metrics = np.mean(metrics, axis=0)
    metrics *= 100
    print('''\
Accuracy: {0}
Accuracy Class: {1}
Mean IU: {2}
FWAV Accuracy: {3}'''.format(*metrics))

    viz = fcn.utils.get_tile_image(visualizations)
    skimage.io.imsave('viz_evaluate.png', viz)


if __name__ == '__main__':
    main()
