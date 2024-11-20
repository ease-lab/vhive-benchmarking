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

import itertools
import logging as log
import numpy as np
import pickle
import sklearn.datasets as datasets
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import  cross_val_predict
from sklearn.model_selection import StratifiedShuffleSplit

def generate_dataset():
    n_samples = 1000
    n_features = 1024
    X, y = datasets.make_classification(n_samples,
                                        n_features,
                                        n_redundant=0,
                                        n_clusters_per_class=2,
                                        weights=[0.9, 0.1],
                                        flip_y=0.1,
                                        random_state=42)
    return {'features': X, 'labels': y}

def generate_hyperparam_sets(param_config):
    keys = list(param_config.keys())
    values = [param_config[k] for k in keys]
    for elements in itertools.product(*values):
        yield dict(zip(keys, elements))

class Driver:
    def __init__(self, XDTconfig=None):
        bucket = os.getenv('BUCKET_NAME', 'vhive-tuning')
        self.storageBackend = Storage(bucket, XDTconfig)

    def handler_broker(self, event, context):
        dataset = generate_dataset()
        hyperparam_config = {
            'model': 'RandomForestRegressor',
            'params': {
                'n_estimators': [5, 10, 20],
                'min_samples_split': [2, 4],
                'random_state': [42]
            }
        }
        models_config = {
            'models': [
                {
                    'model': 'RandomForestRegressor',
                    'params': hyperparam
                } for hyperparam in generate_hyperparam_sets(hyperparam_config['params'])
            ]
        }
        key = self.storageBackend.put('dataset_key', pickle.dumps(dataset))
        return {
            'dataset_key': key,
            'models_config': models_config
        }

    def drive(self, driveArgs):
        event = self.handler_broker({}, {})
        models = event['models_config']['models']
        while len(models) > 1:
            sample_rate = 1 / len(models)
            log.info(f"Running {len(models)} models at sample rate {sample_rate}")

            training_responses = []
            for count, model_config in enumerate(models):
                training_responses.append(
                    driveArgs['trainerfn']({
                        'dataset_key': event['dataset_key'],
                        'model_config': model_config,
                        'count': count,
                        'sample_rate': sample_rate
                    })
                )

            # Keep models with the best score
            top_number = len(training_responses) // 2
            sorted_responses = sorted(training_responses, key=lambda result: result['score'], reverse=True)
            models = [resp['params'] for resp in sorted_responses[:top_number]]

        log.info(f"Training final model {models[0]} on the full dataset")
        final_response = driveArgs['trainerfn']({
            'dataset_key': event['dataset_key'],
            'model_config': models[0],
            'count': 0,
            'sample_rate': 1.0
        })
        log.info(f"Final result: score {final_response['score']}, model {final_response['params']['model']}")
        return
