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

class Metatrainer:
    def __init__(self, XDTconfig=None):
        bucket = os.getenv('BUCKET_NAME', 'vhive-stacking')
        self.storageBackend = Storage(bucket, XDTconfig)

    def metatrain(self, metatrainCfg):
        with tracing.Span("Get the inputs"):
            dataset = pickle.loads(self.storageBackend.get(metatrainCfg['dataset_key']))
            meta_features = pickle.loads(self.storageBackend.get(metatrainCfg['meta_features_key']))
            models = pickle.loads(self.storageBackend.get(metatrainCfg['models_key']))

        log.info("Init meta model")
        model_class = model_dispatcher(metatrainCfg['model_config']['model'])
        meta_model = model_class(*metatrainCfg['model_config']['params'])
        with tracing.Span("Train the meta model"):
            log.info("Train meta model and get predictions")
            meta_predictions = cross_val_predict(meta_model, meta_features, dataset['labels'], cv=5)
            score = roc_auc_score(meta_predictions, dataset['labels'])

            log.info(f"Ensemble model score {score}")
            meta_model.fit(meta_features, dataset['labels'])

        with tracing.Span("Put the full model and predictions"):
            model_full = {'models': models, 'meta_model': meta_model}
            mpkey = self.storageBackend.put('meta_predictions_key', pickle.dumps(meta_predictions))
            mfkey = self.storageBackend.put('model_full_key', pickle.dumps(model_full))

        return {
            'model_full_key': mfkey,
            'meta_predictions_key': mpkey,
            'score': str(score)
        }
