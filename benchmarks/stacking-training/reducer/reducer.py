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

class Reducer:
    def __init__(self, XDTconfig=None):
        bucket = os.getenv('BUCKET_NAME', 'vhive-stacking')
        self.storageBackend = Storage(bucket, XDTconfig)

    def reduce(self, reducerCfg):
        log.info("Reducer is invoked")
        models, predictions = [], []
        for i in range(len(reducerCfg['model_keys'])):
            with tracing.Span(f"Reducer gets model {i} from S3"):
                mkey = reducerCfg['model_keys'][i]
                pkey = reducerCfg['prediction_keys'][i]
                models.append(pickle.loads(self.storageBackend.get(mkey)))
                predictions.append(pickle.loads(self.storageBackend.get(pkey)))

        meta_features = np.transpose(np.array(predictions))
        mfkey = self.storageBackend.put('meta_features', pickle.dumps(meta_features))
        mkey = self.storageBackend.put('models', pickle.dumps(models))
        return {'models_key': mkey, 'meta_features_key': mfkey}
