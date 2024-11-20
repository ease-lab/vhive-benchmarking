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
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import  cross_val_predict
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedShuffleSplit

def model_dispatcher(model_name):
	if model_name=='LinearSVR':
		return LinearSVR
	elif model_name=='LinearRegression':
		return LinearRegression
	elif model_name=='RandomForestRegressor':
		return RandomForestRegressor
	elif model_name=='KNeighborsRegressor':
		return KNeighborsRegressor
	elif model_name=='LogisticRegression':
		return LogisticRegression
	else:
		raise ValueError(f"Model {model_name} not found")

class Trainer:
    def __init__(self, XDTconfig=None):
        bucket = os.getenv('BUCKET_NAME', 'vhive-tuning')
        self.storageBackend = Storage(bucket, XDTconfig)

    def train(self, args):
        dataset = pickle.loads(self.storageBackend.get(args['dataset_key']))
        with tracing.Span("Training a model"):
            # Init model
            model_class = model_dispatcher(args['model_config']['model'])
            model = model_class(**args['model_config']['params'])

            # Train model and get predictions
            X = dataset['features']
            y = dataset['labels']
            if args['sample_rate'] == 1.0:
                X_sampled, y_sampled = X, y
            else:
                strat_split = StratifiedShuffleSplit(n_splits=1, train_size=args['sample_rate'], random_state=42)
                sampled_index, _ = list(strat_split.split(X, y))[0]
                X_sampled, y_sampled = X[sampled_index], y[sampled_index]

            y_pred = cross_val_predict(model, X_sampled, y_sampled, cv=5)
            model.fit(X_sampled, y_sampled)
            score = roc_auc_score(y_sampled, y_pred)
            log.info(f"{args['model_config']['model']}, params: {args['model_config']['params']}, dataset size: {len(y_sampled)},score: {score}")

            mkey = f"model_{args['count']}"
            pkey = f"pred_model_{args['count']}"
            model_key = self.storageBackend.put(mkey, pickle.dumps(model))
            pred_key = self.storageBackend.put(pkey, pickle.dumps(y_pred))

            return {'model_key': model_key, 'pred_key': pred_key, 'score': score}
