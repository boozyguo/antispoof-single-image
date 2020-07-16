#!/usr/bin/env python3
#-*- coding:utf-8 -*-

import os
import cv2
import time
import torch
import random
import argparse
import numpy as np
from torch.nn import functional as F

import core as corelib
import dataset as dlib

from IPython import embed

class LGSCInfer(object):

    def __init__(self, args):

        self.args     = args
        self.model    = dict()
        self.softmax  = torch.nn.Softmax(dim=1)
        self.use_cuda = args.use_gpu and torch.cuda.is_available()
        self._model_loader()

    def _model_loader(self):
        
        self.model['transform'] = dlib.get_test_augmentations()
        self.model['lgsc'] = corelib.LGSC(drop_ratio=self.args.drop_ratio)
        self.model['triplet'] = corelib.TripletLoss(margin=self.args.margin)

        if self.use_cuda:
            self.model['lgsc'] = self.model['lgsc'].cuda()
            if len(self.args.gpu_ids) > 1:
                self.model['lgsc'] = torch.nn.DataParallel(self.model['lgsc'], device_ids=self.args.gpu_ids)
                print('Parallel mode is going ...')

        if len(self.args.resume) > 3:
            checkpoint = torch.load(self.args.resume, map_location=lambda storage, loc: storage)
            self.args.start_epoch = checkpoint['epoch']
            self.model['lgsc'].load_state_dict(checkpoint['backbone'])
            print('Resuming the train process at %3d epoches ...' % self.args.start_epoch)
        self.model['lgsc'].eval()   # core
        
        print('Model loading was finished ...')


    def calc_losses(self, outs, clf_out, target):
        ''' calculte the loss for LGSC '''

        clf_loss = F.cross_entropy(clf_out, target) * self.args.loss_coef['clf_loss']
        cue_feat = target.reshape(-1, 1, 1, 1).float() * outs[-1]
        num_reg  = (torch.sum(target) * np.prod(cue_feat.shape[1:])).type(torch.float)
        reg_loss = (torch.sum(torch.abs(cue_feat)) / (num_reg + 1e-9)) * self.args.loss_coef['reg_loss']

        trip_loss = 0
        batchsize = outs[-1].shape[0]
        for feat in outs[:-1]:
            feat = F.adaptive_avg_pool2d(feat, [1, 1]).view(batchsize, -1)
            trip_loss += self.model['triplet'](feat, target) * self.args.loss_coef['trip_loss']
        total_loss = clf_loss + reg_loss + trip_loss
        return total_loss
        
    
    def visual_cue(self, img, cue):
        
        b, c, h, w = img.shape
        vispair = np.zeros((h, 2 * w, c), dtype=np.uint8)
        img = img[0].permute(1, 2, 0)
        img = (img - img.min()) / (img.max() - img.min()) * 255
        cue = cue[0].permute(1, 2, 0)
        cue = (cue - cue.min()) / (cue.max() - cue.min()) * 255
        vispair[:, :w, :] = img.numpy().astype(np.uint8)
        vispair[:, w:, :] = cue.cpu().numpy().astype(np.uint8)
        return vispair
    
    
    def infer(self, image, save_path = ''):
        
        image = self.model['transform'](image=image)['image'].unsqueeze(0)
        with torch.no_grad():
            
            imgs_feat, clf_out = self.model['lgsc'](image)
            spoof_score = torch.mean(torch.abs(imgs_feat[-1])).item()
            print('%-16s, cue_spoof_score %.4f' % (save_path.split('/')[-1], spoof_score))
            save_path = ''
            if len(save_path) > 0:
                vispair = self.visual_cue(image, imgs_feat[-1])
                cv2.imwrite(save_path, vispair)
                
        

        
cp_dir = '/home/jovyan/jupyter/checkpoints_zoo/face-antisp/single-1.0/siw_baseline/sota.pth' 

def infer_args():

    parser = argparse.ArgumentParser(description='PyTorch of antispoof-single-image')

    # -- env
    parser.add_argument('--use_gpu', type=bool, default=True)
    parser.add_argument('--gpu_ids', type=list, default=[0, 1])

    # -- model
    parser.add_argument('--in_size',    type=tuple,  default=(224, 224))   # FIXED
    parser.add_argument('--drop_ratio', type=float,  default=0.4)          # TODO
    parser.add_argument('--margin',     type=float,  default=0.5)          # paper-setting
    parser.add_argument('--loss_coef',  type=dict,   default={'clf_loss':5.0, 'reg_loss':5.0, 'trip_loss':1.0}) # paper-setting

    # -- checkpoint
    parser.add_argument('--resume', type=str, default=cp_dir)
     
    args = parser.parse_args()

    return args        
        
        
        
if __name__ == "__main__":
    
    # input = torch.randn(1, 3, 224, 224)
    # input = torch.from_numpy(np.load('input.npy')).cuda()
    # print(input.shape)
    lgsc = LGSCInfer(args=infer_args())
    input = cv2.imread('imgs/live.jpg')
    lgsc.infer(input)
    # lgsc.infer(input)
#     lgsc.model['lgsc'].eval()
#     lgsc.model['lgsc'].module.encoder.eval()
#     lgsc.model['lgsc'].module.decoder.eval()
#     lgsc.model['lgsc'].module.auxcfer.resnet18.fc.eval()
#     lgsc.model['lgsc'].module.auxcfer.dropout.eval()
    
    # lgsc.model['lgsc'].train()
#     for i in range(5):
        
#         print('%s' % (36 * '*'))
        
        # lgsc.model['lgsc'].eval()
#         imgs_feat, clf_out = lgsc.model['lgsc'](input)
#         print(clf_out.cpu().detach().numpy())
#         outs = lgsc.model['lgsc'].module.encoder(input)
#         print('encoder : %f' % torch.mean(outs[-1]).item())
#         outs = lgsc.model['lgsc'].module.decoder(outs)
#         print('decoder : %f' % torch.mean(outs[-1]).item())
#         print(sum(outs[-1][0]))
#         clfo = lgsc.model['lgsc'].module.auxcfer(outs[-1])
#         print('auxcfer : ', clfo.cpu().detach().numpy())

#     files = ['live.jpg', 'printsp.jpg', 'videoplay.jpg']
#     for i in range(5):
        
#         # random.shuffle(files)
#         for file in files:
            
#             img = cv2.imread(os.path.join('imgs/', file))
#             save_path = 'imgs/cue_%s' % file
#             lgsc.infer(img, save_path)
    
    