# MIT License
#
# Copyright (c) 2022 Alan Nair and The vHive Ecosystem
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os

from storage import Storage
import tracing

import logging as log
import numpy as np
import pickle
import sklearn.datasets as datasets
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import LinearSVR
from sklearn.linear_model import LinearRegression, Lasso
from sklearn.model_selection import cross_val_predict
from sklearn.metrics import roc_auc_score

def model_dispatcher(model_name):
    if model_name == 'LinearSVR':
        return LinearSVR
    elif model_name == 'Lasso':
        return Lasso
    elif model_name == 'LinearRegression':
        return LinearRegression
    elif model_name == 'RandomForestRegressor':
        return RandomForestRegressor
    elif model_name == 'KNeighborsRegressor':
        return KNeighborsRegressor
    elif model_name == 'LogisticRegression':
        return LogisticRegression
    else:
        raise ValueError(f"Model {model_name} not found")

class Trainer:
    def __init__(self, XDTconfig=None):
        bucket = os.getenv('BUCKET_NAME','vhive-stacking')
        self.storageBackend = Storage(bucket, XDTconfig)

    def train(self, trainCfg):
        log.info("Trainer %d is invoked" % (trainCfg['trainer_id']))
        dataset = pickle.loads(self.storageBackend.get(trainCfg['dataset_key']))

        with tracing.Span("Training a model"):
            model_config = trainCfg['model_cfg']
            model_class = model_dispatcher(model_config['model'])
            model = model_class(**model_config['params'])
            y_pred = cross_val_predict(model, dataset['features'], dataset['labels'], cv=5)
            model.fit(dataset['features'], dataset['labels'])
            log.info(f"{model_config['model']} score: {roc_auc_score(dataset['labels'], y_pred)}")

        mkey = 'model_%d' % (trainCfg['trainer_id'])
        pkey = 'pred_model_%d' % (trainCfg['trainer_id'])
        model_key = self.storageBackend.put(mkey, pickle.dumps(model))
        pred_key = self.storageBackend.put(pkey, pickle.dumps(y_pred))

        return {'model_key': model_key, 'pred_key': pred_key}
