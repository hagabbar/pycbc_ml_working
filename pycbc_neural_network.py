#Simple Multilayer Neural Network to seperate pycbc injections from noise triggers
#Author: Hunter Gabbard
#Max Planck Insitute for Gravitational Physics
#How to use only one GPU device....export CUDA_VISIBLE_DEVICES="0" in command line prior to run
#How to run in the background from the command line...python simple_neural_network.py -d NSBH01_ifar0-1.hdf,NSBH02_ifar0-1.hdf >/dev/null 2>err.txt &

from __future__ import division
import argparse
import keras
from keras.models import Sequential
from keras.layers import LSTM, Dense
import numpy as np
import h5py
from keras.models import Sequential
from keras.layers import Dense, Activation, GaussianDropout, Dropout, ActivityRegularization
from keras.optimizers import RMSprop
from keras.layers.normalization import BatchNormalization
import sys
import os
from math import exp, log
import tensorflow as tf
from keras.callbacks import EarlyStopping
from matplotlib import use
use('Agg')
from matplotlib import pyplot as pl
import datetime
import unicodedata


#Definition for loading in dataset parameters into variables and then combine into a numpy array
def load_back_data(data, params):
    print 'loading background triggers'
    dict_comb = {}
    back = {}
    tmp_comb = {}
    for fi in data:
        print fi
        h1 = h5py.File(fi, 'r')
        ifo = unicodedata.normalize('NFKD', h1.keys()[0]).encode('ascii','ignore')
        if data[0] == fi:
            for label in h1['%s' % ifo].keys():
                for key in params:
                    if label == key:
                        if key == 'delta_chirp' or key == 'time':
                            dict_comb[label] = np.asarray(h1['%s/%s' % (ifo,label)][:]).reshape((h1['%s/%s' % (ifo,label)].shape[0],1))
                        else:
                            dict_comb[label] = np.asarray(h1['%s/%s' % (ifo,label)][:]).reshape((h1['%s/%s' % (ifo,label)].shape[0],1))
                            back[label] = np.asarray(h1['%s/%s' % (ifo,label)][:]).reshape((h1['%s/%s' % (ifo,label)].shape[0],1))
        else:
            for label in h1['%s' % ifo].keys():
                for key in params:
                    if label == key:
                        if key == 'delta_chirp' or key == 'time':
                            tmp_comb[label+'_new'] = np.asarray(h1['%s/%s' % (ifo,label)][:]).reshape((h1['%s/%s' % (ifo,label)].shape[0],1))
                            dict_comb[label] = np.vstack((dict_comb[label], tmp_comb[label+'_new']))
                        else:                   
                            tmp_comb[label+'_new'] = np.asarray(h1['%s/%s' % (ifo,label)][:]).reshape((h1['%s/%s' % (ifo,label)].shape[0],1))
                            back[label] = np.vstack((back[label], tmp_comb[label+'_new']))
                            dict_comb[label] = np.vstack((dict_comb[label], tmp_comb[label+'_new']))
    print params
    for idx,key in enumerate(params):
        if key == 'delta_chirp' or key == 'time':
            continue
        elif idx == 0:
            back_comb = back[key]
       
        else:
            back_comb = np.hstack((back_comb,back[key]))
    return back_comb, dict_comb

#Load CBC/noise triggers from multiple data sets
def load_inj_data(data, params, dict_comb):
    tmp_comb = {}
    inj = {}
    print 'loading injections'
    for fi in data:
        h1 = h5py.File(fi, 'r')
        ifo = unicodedata.normalize('NFKD', h1.keys()[0]).encode('ascii','ignore')
        if data[0] == fi:
            for label in h1['%s' % ifo].keys():
                for key in params:
                    if label == key:
                        if key == 'delta_chirp_inj' or key == 'time_inj' or key == 'dist_inj':
                            dict_comb[label] = np.asarray(h1['%s/%s' % (ifo,label)][:]).reshape((h1['%s/%s' % (ifo,label)].shape[0],1))
                        else:
                            dict_comb[label] = np.asarray(h1['%s/%s' % (ifo,label)][:]).reshape((h1['%s/%s' % (ifo,label)].shape[0],1))
                            inj[label] = np.asarray(h1['%s/%s' % (ifo,label)][:]).reshape((h1['%s/%s' % (ifo,label)].shape[0],1))
        else:
            for label in h1['%s' % ifo].keys():
                for key in params:
                    if label == key:
                        if key == 'delta_chirp_inj' or key == 'time_inj' or key == 'dist_inj':
                            tmp_comb[label+'_new'] = np.asarray(h1['%s/%s' % (ifo,label)][:]).reshape((h1['%s/%s' % (ifo,label)].shape[0],1))
                            dict_comb[label] = np.vstack((dict_comb[label], tmp_comb[label+'_new']))
                        else:
                            tmp_comb[label+'_new'] = np.asarray(h1['%s/%s' % (ifo,label)][:]).reshape((h1['%s/%s' % (ifo,label)].shape[0],1))
                            inj[label] = np.vstack((inj[label], tmp_comb[label+'_new']))
                        dict_comb[label] = np.vstack((dict_comb[label], tmp_comb[label+'_new']))

    for idx,key in enumerate(params):
        if key  == 'delta_chirp_inj' or key == 'time_inj' or key == 'dist_inj':
            continue
        elif idx == 0:
            print params
            inj_comb = inj[key]
        else:
            inj_comb = np.hstack((inj_comb,inj[key]))
    return inj_comb, dict_comb

#Generate injection weights
def inj_weight_calc(dict_comb):
    print 'calculating injection weights'
    inj_weights_pre = []
    np.asarray(inj_weights_pre)
    dist_inj = dict_comb['dist_inj']
    dist_inj_mean = (dist_inj**2).mean()
    for idx in enumerate(dict_comb['delta_chirp_inj']):
        idx = idx[0]
        inj_weights_pre.append((dist_inj[idx][0]**2)/dist_inj_mean)

    inj_weights = np.asarray(inj_weights_pre).reshape((dict_comb['delta_chirp_inj'].shape[0],1))

    return inj_weights

def orig_norm(back_trig, inj_trig, tt_split):
    print 'storing original trigger values prior to normalization'
    comb_all = np.vstack((back_trig, inj_trig))
    indices_trig = np.random.permutation(back_trig.shape[0])
    trig_train_idx, trig_test_idx = indices_trig[:int(back_trig.shape[0]*tt_split)], indices_trig[int(back_trig.shape[0]*tt_split):int(back_trig.shape[0])]
    trig_train_p, trig_test_p = back_trig[trig_train_idx,:], back_trig[trig_test_idx,:]
    indices_inj = np.random.permutation(inj_trig.shape[0])
    inj_train_idx, inj_test_idx = indices_inj[:int(inj_trig.shape[0]*tt_split)], indices_inj[int(inj_trig.shape[0]*tt_split):]
    inj_train_p, inj_test_p = inj_trig[inj_train_idx,:], inj_trig[inj_test_idx,:]
    train_data_p = np.vstack((trig_train_p, inj_train_p))
    test_data_p = np.vstack((trig_test_p, inj_test_p))

    return train_data_p, test_data_p, comb_all

def sep(trig_comb,inj_comb,indices_trig,tt_split, inj_weights):
    print 'seperating into training/testing sets'
    trig_train_idx, trig_test_idx = indices_trig[:int(trig_comb.shape[0]*tt_split)], indices_trig[int(trig_comb.shape[0]*tt_split):int(trig_comb.shape[0])]
    trig_train, trig_test = trig_comb[trig_train_idx,:], trig_comb[trig_test_idx,:]
    indices_inj = np.random.permutation(inj_comb.shape[0])
    inj_train_idx, inj_test_idx = indices_inj[:int(inj_comb.shape[0]*tt_split)], indices_inj[int(inj_comb.shape[0]*tt_split):]
    inj_train_weight, inj_test_weight = inj_weights[inj_train_idx,:], inj_weights[inj_test_idx,:]
    inj_train, inj_test = inj_comb[inj_train_idx,:], inj_comb[inj_test_idx,:]
    train_data = np.vstack((trig_train, inj_train))
    test_data = np.vstack((trig_test, inj_test))

    return train_data, test_data, trig_test, inj_test, inj_test_weight, inj_train_weight

def normalize(trig_comb,comb_all,pre_proc_log):
    print 'normalizing features'
    for idx in range(0,comb_all.shape[1]):
       if pre_proc_log[idx] == True:
           if idx == 0:
               tmp_trig_comb = ((np.log(comb_all[:,idx]) - np.log(comb_all[:,idx]).mean())/np.log(comb_all[:,idx]).max()).reshape((comb_all.shape[0],1))
               tmp_inj_comb = tmp_trig_comb[trig_comb.shape[0]:]           
               tmp_trig_comb = tmp_trig_comb[0:trig_comb.shape[0]]
               continue
           else:
               tmp = ((np.log(comb_all[:,idx]) - np.log(comb_all[:,idx]).mean())/np.log(comb_all[:,idx]).max()).reshape((comb_all.shape[0],1))
       elif pre_proc_log[idx] == False:
           if idx == 0:
               tmp_trig_comb = ((comb_all[:,idx] - comb_all[:,idx].mean())/comb_all[:,idx].max()).reshape((comb_all.shape[0],1))
               tmp_inj_comb = tmp_trig_comb[trig_comb.shape[0]:]
               tmp_trig_comb = tmp_trig_comb[0:trig_comb.shape[0]]
               continue
           else:
               tmp = ((comb_all[:,idx] - comb_all[:,idx].mean())/comb_all[:,idx].max()).reshape((comb_all.shape[0],1))

       tmp_trig_comb = np.hstack((tmp_trig_comb,tmp[0:trig_comb.shape[0]])) 
       tmp_inj_comb = np.hstack((tmp_inj_comb,tmp[trig_comb.shape[0]:])) 
    comb_all = np.vstack((tmp_trig_comb, tmp_inj_comb)) 

    return tmp_trig_comb, tmp_inj_comb, comb_all    

def costco_label_maker(back_trig, inj_trig, tt_perc):
    print 'bought a label maker for my nn, it\'s pretty nice'
    #making labels (zero is noise, one is injection)
    c_zero = np.zeros((back_trig.shape[0],1))
    c_z_train = c_zero[:int(back_trig.shape[0]*tt_perc)]
    c_z_test = c_zero[int(back_trig.shape[0]*tt_perc):int(back_trig.shape[0])]
    c_ones = np.ones((int(inj_trig.shape[0]),1))
    c_o_train = c_ones[:int(inj_trig.shape[0]*tt_perc)]
    c_o_test = c_ones[int(inj_trig.shape[0]*tt_perc):int(inj_trig.shape[0])]
    lab_train = np.vstack((c_z_train,c_o_train))
    lab_test = np.vstack((c_z_test,c_o_test))
    labels_all = np.vstack((c_zero,c_ones))
 
    return lab_train, lab_test, labels_all

def samp_weight(trig_comb,inj_comb,inj_train_weight,inj_test_weight):
    print 'making sample weights vector'
    trig_weights = np.zeros((trig_comb.shape[0],1))
    trig_weights.fill(1/((trig_comb.shape[0])/(inj_comb.shape[0])))
    trig_w_train = trig_weights[:int(trig_comb.shape[0]*.7)]
    trig_w_test = trig_weights[int(trig_comb.shape[0]*.7):]
    train_weights = np.vstack((trig_w_train,inj_train_weight)).flatten()
    test_weights = np.vstack((trig_w_test,inj_test_weight)).flatten()

    return train_weights, test_weights

def the_machine(learning_rate, trig_comb, nb_epoch, batch_size, train_weights, test_weights, train_data, test_data, lab_train, lab_test, out_dir, now):
    print 'It\'s is alive!!!'
    model = Sequential()
    drop_rate = 0.2
    ret_rate = 1 - drop_rate
    act = keras.layers.advanced_activations.LeakyReLU(alpha=0.01)                       #LeakyReLU(alpha=0.1)
    #early_stopping = EarlyStopping(monitor='val_loss', patience=2)

    #7 is the number of features used. This value may change in the future
    model.add(Dense(int(8./ret_rate), input_dim=trig_comb.shape[1])) #10
    model.add(BatchNormalization())
    act
    model.add(GaussianDropout(drop_rate))

    model.add(Dense(int(8./ret_rate))) #7
    model.add(BatchNormalization())
    act
    model.add(GaussianDropout(drop_rate))

    model.add(Dense(int(8./ret_rate))) #3
    model.add(BatchNormalization())
    act
    model.add(GaussianDropout(drop_rate))

    model.add(Dense(int(8./ret_rate))) #3
    model.add(BatchNormalization())
    act
    model.add(GaussianDropout(drop_rate))

    model.add(Dense(int(8./ret_rate))) #3
    model.add(BatchNormalization())
    act
    model.add(GaussianDropout(drop_rate))

    model.add(Dense(int(8./ret_rate))) #3
    model.add(BatchNormalization())
    act
    model.add(GaussianDropout(drop_rate))

    model.add(Dense(1, init='normal'))
    model.add(Activation('sigmoid'))

    #Compiling model
    print("[INFO] compiling model...")
    rmsprop = RMSprop(lr=learning_rate)  #default is 0.001
    model.compile(loss="binary_crossentropy", optimizer=rmsprop,
            metrics=["accuracy","binary_crossentropy"], class_mode='binary')
   
    #model.fit(train_data, lab_train, nb_epoch=1, batch_size=32, sample_weight=train_weights, shuffle=True, show_accuracy=True)
    hist = model.fit(train_data, lab_train,
                        nb_epoch=nb_epoch, batch_size=batch_size,    #66000
                        sample_weight=train_weights,
                        validation_data=(test_data,lab_test,test_weights),
                        shuffle=True, show_accuracy=True)
    #print(hist.history) 

    # show the accuracy on the testing set
    print("[INFO] evaluating on testing set...")
    eval_results = model.evaluate(test_data, lab_test,
                                        sample_weight=test_weights,
                                            batch_size=batch_size, verbose=1)
    print("[INFO] loss={:.4f}, accuracy: {:.4f}%".format(eval_results[0],
            eval_results[1] * 100))
    #Saving prediction probabilities to a variable
    res_pre = model.predict(test_data)

    #Printing summary of model parameters
    model.summary()

    #Saving model to hdf file for later use
    model.save('%s/run_%s/nn_model.hdf' % (out_dir,now))
    np.save('%s/run_%s/hist.npy' % (out_dir,now), hist.history)

    return res_pre, eval_results, hist, model

#Function to compute ROC curve for both newsnr and some other score value
def ROC_inj_and_newsnr(run_num,batch_size,trig_test,test_data,inj_test_weight,inj_test,lab_test,out_dir,now,model):
    print 'generating ROC curve plot' 

    n_noise = len(trig_test)
    pred_prob = model.predict_proba(test_data, batch_size=batch_size).T[0]
    prob_sort_noise = pred_prob[pred_prob[0:n_noise].argsort()][::-1]
    prob_sort_inj = pred_prob[n_noise:][pred_prob[n_noise:].argsort()][::-1]
    prob_sort_injWeight = inj_test_weight.T[0][pred_prob[n_noise:].argsort()][::-1]
    prob_sort_injNewsnr = inj_test[:,2][pred_prob[n_noise:].argsort()][::-1]
    newsnr_sort_noiseNewsnr = trig_test[:,2][trig_test[:,2][0:].argsort()][::-1]
    newsnr_sort_injNewsnr = inj_test[:,2][inj_test[:,2][0:].argsort()][::-1]
    newsnr_sort_injWeight = inj_test_weight.T[0][inj_test[:,2][0:].argsort()][::-1]
    pred_class = model.predict_classes(test_data, batch_size=batch_size)
    class_sort = pred_class[pred_prob[:].argsort()][::-1]
    orig_test_labels = lab_test[pred_prob[:].argsort()][::-1]


    #Initialize variables/arrays
    w_sum = 0
    newsnr_sum = 0
    FAP = []
    ROC_w_sum = []
    ROC_newsnr_sum = []

    for idx in range(n_noise):
        #Calculate false alarm probability value
        FAP.append((float(idx+1))/n_noise)

        #Compute sum
        w_sum = prob_sort_injWeight[prob_sort_inj >= prob_sort_noise[idx]].sum()
        newsnr_sum = newsnr_sort_injWeight[newsnr_sort_injNewsnr >= newsnr_sort_noiseNewsnr[idx]].sum()
      
        #Append
        ROC_w_sum.append(w_sum)
        ROC_newsnr_sum.append(newsnr_sum)

    #Normalize ROC y axis
    ROC_w_sum = np.asarray(ROC_w_sum)
    ROC_w_sum *= (1.0/ROC_w_sum.max())
    ROC_newsnr_sum = np.asarray(ROC_newsnr_sum)
    ROC_newsnr_sum *= (1.0/ROC_newsnr_sum.max())
        
    #Plot ROC Curve
    pl.figure(run_num)
    pl.plot(FAP,ROC_w_sum,label='NN Score')
    pl.plot(FAP,ROC_newsnr_sum,label='New SNR')
    pl.ylim(ymax=1.)
     
    pl.legend(frameon=True, loc='lower right')
    #pl.title('ROC Curve')
    pl.xlabel('False alarm probability')
    pl.ylabel('Relative detection rate')
    pl.xscale('log')
    pl.savefig('%s/run_%s/ROC_curve.png' % (out_dir,now))
    pl.close()

    return ROC_w_sum, ROC_newsnr_sum, FAP, pred_prob, prob_sort_noise, prob_sort_inj

#Function to compute ROC cruve given any weight and score. Not currently used, but could be used later if desired
def ROC(inj_weight, inj_param, noise_param, out_dir, now):
    print 'generating ROC curve plot'
    
    #Initialize variables/arrays
    ROC_value = 0
    FAP = []
    np.array(FAP)
    ROC_sum = []
    np.array(ROC_sum)

    for idx in range(len(noise_param)):
        #Calculate false alarm probability value
        FAP.append((float(idx+1))/len(noise_param))

        #Compute sum
        ROC_value = inj_weight[inj_param >= noise_param[idx]].sum()

        #Append
        ROC_sum.append(ROC_value)

        #Normalize ROC y axis
        ROC_sum = np.asarray(ROC_sum)
        ROC_sum *= (1.0/ROC_sum.max())

    #Plot ROC Curve
    pl.plot(FAP,ROC_sum,label='Score')
    pl.legend(frameon=True)
    pl.title('ROC Curve')
    pl.xlabel('False Alarm Probability')
    pl.ylabel('Weighted Sum')
    pl.xscale('log')
    pl.savefig('%s/run_%s/ROC_curve.png' % (out_dir,now))
    pl.close()


    return ROC_sum, FAP

def feature_hists(run_num, out_dir, now, params, pre_proc_log, nn_train, nn_test, train_data, test_data):
    print 'plotting feature histograms'
    for idx, lab in enumerate(zip(params, pre_proc_log)):
        for data, noise_len, dtype in zip([train_data, test_data], [nn_train, nn_test], ['train', 'test']):
            pl.figure(run_num+idx)
            hist_1, bins_1 = np.histogram(data[0:noise_len,idx], bins=100, density=True)
            hist_2, bins_2 = np.histogram(data[noise_len:,idx], bins=100, density=True)
            # print lab[0], dtype, 'bg', bins_1.min(), bins_1.max(), 'inj', bins_2.min(), bins_2.max()
            width_1 = (bins_1[1] - bins_1[0])
            width_2 = (bins_2[1] - bins_2[0])
            center_1 = (bins_1[:-1] + bins_1[1:]) / 2
            center_2 = (bins_2[:-1] + bins_2[1:]) / 2
            pl.bar(center_1, hist_1, log=True, label='background',color='b', alpha=0.6, align='center', width=width_1)
            pl.bar(center_2, hist_2, log=True, label='injection', color='r', alpha=0.6, align='center', width=width_2)
            pl.ylim(ymin=1e-4)
            pl.legend(frameon=True)
            if lab[1]:
               # pl.title('log(%s) histogram' % lab[0])
                pl.xlabel('log(%s) [normalized]' % lab[0])
            else:
               # pl.title('%s histogram' % lab[0])
                pl.xlabel('%s [normalized]' % lab[0])
            pl.savefig('%s/run_%s/histograms/%s_%s.png' % (out_dir, now, lab[0], dtype))
            pl.close()

def main_plotter(prob_sort_noise, prob_sort_inj, run_num, out_dir, now, test_data_p, params, back_test, hist, pred_prob, pre_proc_log):

    print 'plotting training metrics'
    print hist.history.keys()
    for i, metric in enumerate(['loss', 'acc', 'binary_crossentropy']):
        mname = metric.replace('acc', 'accuracy')
        pl.figure(run_num+i)
        pl.plot(hist.history[metric], label='Training', alpha=0.4)
        pl.plot(hist.history['val_'+metric], label='Validation', alpha=0.4)
        pl.legend(frameon=True, loc='center right')
        pl.xlabel('Epoch')
        pl.ylabel(mname.replace('_', ' '))
        pl.ylim(ymin=0.)
        pl.savefig('%s/run_%s/%s_vs_epoch.png' % (out_dir, now, mname[0:4]))
        pl.close()

    print 'plotting histograms of score values'
    pl.figure(run_num+2)
    numpy_hist_1, bins_1 = np.histogram(prob_sort_noise, bins=100, density=True)
    numpy_hist_2, bins_2 = np.histogram(prob_sort_inj, bins=100, density=True)
    width_1 = (bins_1[1] - bins_1[0])
    width_2 = (bins_2[1] - bins_2[0])
    center_1 = (bins_1[:-1] + bins_1[1:]) / 2
    center_2 = (bins_2[:-1] + bins_2[1:]) / 2
    pl.bar(center_1, numpy_hist_1, log=True, label='background',color='b', alpha=0.6, align='center', width=width_1)
    pl.bar(center_2, numpy_hist_2, log=True, label='injection', color='r', alpha=0.6, align='center', width=width_2)
    pl.ylim(ymin=1e-4)
    pl.legend(frameon=True)
    pl.savefig('%s/run_%s/score_hist.png' % (out_dir,now))
    pl.close()

    n_noise = len(back_test)
    for idx,lab in enumerate(zip(params,pre_proc_log)):
        print('plotting score vs. %s' % lab[0])
        pl.figure(run_num+idx)
        pl.scatter(test_data_p[0:n_noise,idx],pred_prob[0:n_noise],marker="o", s=8,c='k',edgecolor='none',label='background',alpha=0.3)
        pl.scatter(test_data_p[n_noise:,idx], pred_prob[n_noise:], marker="^",s=10,c='r',edgecolor='none',label='injection', alpha=0.4)
        pl.legend(frameon=True)
        if lab[1] == True:
            pl.title('Score vs. log(%s)' % lab[0])
            pl.xlabel('log(%s)' % lab[0])
        else:
            pl.title('Score vs. %s' % lab[0])
            pl.xlabel('%s' % lab[0])
        pl.ylabel('Score')
        pl.ylim(0,1)
        pl.savefig('%s/run_%s/score_vs_%s.png' % (out_dir,now,lab[0]))
        pl.close()
      
        for idx2,lab2 in enumerate(zip(params,pre_proc_log)):
             if lab[0] > lab2[0]:
                 print('plotting %s vs. %s' % (lab2[0], lab[0]))
                 pl.figure(run_num)
                 pl.scatter(test_data_p[0:n_noise,idx],test_data_p[0:n_noise,idx2],c=pred_prob[0:n_noise],marker="o",s=10,edgecolor='none',label='background',alpha=0.4)
                 pl.scatter(test_data_p[n_noise:,idx], test_data_p[n_noise:,idx2], c=pred_prob[n_noise:], marker="^",s=10,edgecolor='none',label='injection', alpha=0.4)
                 pl.legend(frameon=True)
                 if lab2[1] == True and lab[1] == True:
                     pl.title('log(%s) vs. log(%s)' % (lab2[0], lab[0]))
                     pl.xlabel('log(%s)' % lab[0])
                     pl.ylabel('log(%s)' % lab2[0])
                 elif lab2[1] == True and lab[1] == False:
                     pl.title('log(%s) vs. %s' % (lab2[0], lab[0]))
                     pl.xlabel('%s' % lab[0])
                     pl.ylabel('log(%s)' % lab2[0])
                 elif lab2[1] == False and lab[1] == True:
                     pl.title('%s vs. log(%s)' % (lab2[0], lab[0]))
                     pl.xlabel('log(%s)' % lab[0])
                     pl.ylabel('%s' % lab2[0])
                 elif lab2[1] == False and lab[1] == False:
                     pl.title('%s vs. %s' % (lab2[0], lab[0]))
                     pl.xlabel('%s' % lab[0])
                     pl.ylabel('%s' % lab2[0])
                 pl.colorbar()
                 pl.savefig('%s/run_%s/colored_plots/%s_vs_%s.png' % (out_dir,now,lab2[0],lab[0]))
                 pl.close()
             else:
                 continue

def alex_invest(inj_test_weights,inj_test,pred_prob):
    newsnr_thresh = 10
    score_thresh = 0.2
    est_volume = inj_test_weights[inj_test[:,2] > newsnr_thresh and pred_prob < score_thresh]
    print('This is the estimated volume of triggers with newsnr grater than %s and score less than %s: %s' % (newsnr_thresh,score_thresh,est_volume))
    
#Main function
def main(): 
    #Configure tensorflow to use gpu memory as needed
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    session = tf.Session(config=config)
    #don't Use seed value of 32 for testing purposes
    #np.random.seed(seed = 32)

    #Get Current time
    cur_time = datetime.datetime.now()       #Get current time for time stamp labels

    #construct the argument parse and parse the arguments
    ap = argparse.ArgumentParser()
    ap.add_argument("-d", "--inj-files", required=True, nargs='+', type=str,
            help="path to injection HDF files")
    ap.add_argument("-b", "--bg-files", required=True, nargs='+', type=str,
            help="path to background HDF files [currently, one inj file per chunk is used as source of bg data])")
    ap.add_argument("-o", "--output-dir", required=True, type=str,
            help="path to output directory")
    ap.add_argument("-t", "--train-perc", required=False, default=0.5, type=float,
            help="Fraction of triggers you want to train (between 0 and 1). Remaining triggers will be used for testing. Default 0.5")
    ap.add_argument("-e", "--nb-epoch", required=False, default=100, type=int,
            help="Number of epochs. Default 100")
    ap.add_argument("-bs", "--batch-size", required=False, default=32, type=int,
            help="Batch size for the training process (number of samples to use in each gradient descent step). Default 32")
    ap.add_argument("-u", "--usertag", required=False, default=cur_time, type=str,
            help="label for given run")
    ap.add_argument("-r", "--run-number", required=False, default=0, type=int,
            help="If performing multiple runs on same machine, specify a unique number for each run (must be greater than zero)")
    ap.add_argument("--learning-rate", type=float, default=0.01,
        help="Learning rate. Default 0.01")
    ap.add_argument("--dropout-fraction", type=float, default=0.,
        help="Amount of Gaussian dropout noise to use in training. Default 0 (no noise)")
    args = ap.parse_args()

    #Initializing parameters
    data_files = args.inj_files
    back_files = args.bg_files
    out_dir = args.output_dir
    #now = datetime.datetime.now()       #Get current time for time stamp labels
    now = args.usertag
    os.makedirs('%s/run_%s' % (out_dir,now))  # Fail early if the dir already exists
    os.makedirs('%s/run_%s/colored_plots' % (out_dir,now))
    os.makedirs('%s/run_%s/histograms' % (out_dir,now))

    back_params = ['marg_l','count_in','maxnewsnr','maxsnr','ratio_chirp','delT','template_duration','count_out','delta_chirp','time']
    inj_params = ['marg_l_inj','count_in_inj','maxnewsnr_inj','maxsnr_inj','ratio_chirp_inj','delT_inj','template_duration_inj','count_out_inj','dist_inj','delta_chirp_inj','time_inj']
    pre_proc_log = [True,True,True,True,True,False,True,False] #True means to take log of feature, False means don't take log of feature during pre-processing
    tt_split = args.train_perc
    nb_epoch = args.nb_epoch
    batch_size = args.batch_size
    run_num = args.run_number

    #Downloading background and injection triggers
    back_trig, dict_comb = load_back_data(back_files, back_params)
    inj_trig, dict_comb = load_inj_data(data_files, inj_params, dict_comb)

    #Getting injection weights for later use in neural network training process
    inj_weights = inj_weight_calc(dict_comb)

    #Storing original trigger feature values prior to normalization
    train_data_p, test_data_p, comb_all = orig_norm(back_trig, inj_trig, tt_split)    

    #Normalizing features from zero to one
    back_trig, inj_trig, comb_all = normalize(back_trig, comb_all, pre_proc_log)

    #Randomizing the order of the background triggers
    indices_trig = np.random.permutation(back_trig.shape[0])

    #Seperating into training/testing sets
    train_data, test_data, back_test, inj_test, inj_test_weight, inj_train_weight = sep(back_trig, inj_trig, indices_trig, tt_split, inj_weights)

    #making labels (zero is noise, one is injection)...better label maker than one you could buy at costco in my opinion
    lab_train, lab_test, labels_all = costco_label_maker(back_trig, inj_trig, tt_split)
    print len(lab_train), len(lab_test), len(labels_all)

    #Creating sample weights vector
    train_weights, test_weights = samp_weight(back_trig, inj_trig, inj_train_weight, inj_test_weight)

    #Plot histograms of features
    feature_hists(run_num, out_dir, now, back_params[:len(back_params)-2], pre_proc_log, sum(lab_train.flatten() == 0), len(back_test), train_data, test_data)

    #training/testing on deep neural network
    res_pre, eval_results, hist, model = the_machine(args.learning_rate, back_trig, nb_epoch, batch_size, train_weights, test_weights, train_data, test_data, lab_train, lab_test, out_dir, now)
    
    #Compute the ROC curve
    ROC_w_sum, ROC_newsnr_sum, FAP, pred_prob, prob_sort_noise, prob_sort_inj = ROC_inj_and_newsnr(run_num,batch_size,back_test,test_data,inj_test_weight,inj_test,lab_test,out_dir,now,model)

    #Score/histogram plots
    main_plotter(prob_sort_noise, prob_sort_inj, run_num, out_dir, now, test_data, back_params[:len(back_params)-2], back_test, hist, pred_prob, pre_proc_log)

    #Write data to an hdf file
    with h5py.File('%s/run_%s/nn_data.hdf' % (out_dir,now), 'w') as hf:
        hf.create_dataset('FAP', data=FAP)
        hf.create_dataset('ROC_w_sum', data=ROC_w_sum)
        hf.create_dataset('pred_prob', data=pred_prob)
        hf.create_dataset('test_data', data=test_data)
        hf.create_dataset('train_data', data=train_data)
        hf.create_dataset('ROC_newsnr_sum', data=ROC_newsnr_sum)
        hf.create_dataset('inj_weights', data=inj_weights)


    print 'and...presto! You\'re done!'
if __name__ == '__main__':
    main()
