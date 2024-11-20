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

from concurrent import futures
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

model_config = {
    'models': [
        {
            'model': 'LinearSVR',
            'params': {
                'C': 1.0,
                'tol': 1e-6,
                'random_state': 42
            }
        },
        {
            'model': 'Lasso',
            'params': {
                'alpha': 0.1
            }
        },
        {
            'model': 'RandomForestRegressor',
            'params': {
                'n_estimators': 2,
                'max_depth': 2,
                'min_samples_split': 2,
                'min_samples_leaf': 2,
                # 'n_jobs': 2,
                'random_state': 42
            }
        },
        {
            'model': 'KNeighborsRegressor',
            'params': {
                'n_neighbors': 20,
            }
        }
    ],
    'meta_model': {
        'model': 'LogisticRegression',
        'params': {}
    }
}

def generate_dataset():
    n_samples = 300
    n_features = 1024
    X, y = datasets.make_classification(n_samples, n_features,
        n_redundant=0, n_clusters_per_class=2, weights=[0.9, 0.1],
        flip_y=0.1, random_state=42)
    return {'features': X, 'labels': y}

class Driver:
    def __init__(self, XDTconfig=None):
        bucket = os.getenv('BUCKET_NAME','vhive-stacking')
        self.dataset = generate_dataset()
        self.modelConfig = model_config
        self.storageBackend = Storage(bucket, XDTconfig)

    def put_dataset(self):
        key = self.storageBackend.put('dataset', pickle.dumps(self.dataset))
        return key

    def train_all(self, dataset_key: str, trainingConfig: dict) -> list:
        log.info("Invoke Trainers")
        with tracing.Span("Invoke all trainers"):
            all_result_futures = []
            num_trainers = trainingConfig['num_trainers']
            trainer = trainingConfig['trainer_function']
            models = self.modelConfig['models']
            training_responses = []

            if not trainingConfig['concurrent_training']:
                for i in range(num_trainers):
                    trainer_metadata = {
                        'dataset_key': dataset_key,
                        'model_cfg': models[i % len(models)],
                        'trainer_id': i
                    }
                    all_result_futures.append(trainer(trainer_metadata))
            else:
                ex = futures.ThreadPoolExecutor(max_workers=num_trainers)
                trainer_metadata_list = [{
                        'dataset_key': dataset_key,
                        'model_cfg': models[i % len(models)],
                        'trainer_id': i
                    } for i in range(num_trainers)
                ]
                all_result_futures = ex.map(trainer, trainer_metadata_list)

            log.info("Retrieveing trained models")
            for result in all_result_futures:
                training_responses.append(result)

        return training_responses

    def get_final(self, outputs: dict):
        log.info("Get the final outputs")
        _ = pickle.loads(self.storageBackend.get(outputs['model_full_key']))
        _ = pickle.loads(self.storageBackend.get(outputs['meta_predictions_key']))
