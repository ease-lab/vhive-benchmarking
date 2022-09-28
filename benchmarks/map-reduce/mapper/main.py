# MIT License
#
# Copyright (c) 2021 Michal Baczun and EASE lab
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
import sys

import boto3
import logging as log

from mapper import MapFunction
import tracing

LAMBDA = os.environ.get('IS_LAMBDA', 'yes').lower() in ['true', 'yes', '1']
TRACE = os.environ.get('ENABLE_TRACING', 'no').lower() in ['true', 'yes', '1', 'on']

if not LAMBDA:
	import grpc
	import argparse
	import socket

	import mapreduce_pb2_grpc
	import mapreduce_pb2
	import destination as XDTdst
	import source as XDTsrc
	import utils as XDTutil

	from concurrent import futures

	parser = argparse.ArgumentParser()
	parser.add_argument("-dockerCompose", "--dockerCompose",
		dest="dockerCompose", default=False, help="Env docker compose")
	parser.add_argument("-sp", "--sp", dest="sp", default="80", help="serve port")
	parser.add_argument("-zipkin", "--zipkin", dest="zipkinURL",
		default="http://zipkin.istio-system.svc.cluster.local:9411/api/v2/spans",
		help="Zipkin endpoint url")

	args = parser.parse_args()

if TRACE:
	# adding python tracing sources to the system path
	sys.path.insert(0, os.getcwd() + '/../proto/')
	sys.path.insert(0, os.getcwd() + '/../../../utils/tracing/python')

	if tracing.IsTracingEnabled():
	    tracing.initTracer("mapper", url=args.zipkinURL)
	    tracing.grpcInstrumentClient()
	    tracing.grpcInstrumentServer()

# constants
S3 = "S3"
XDT = "XDT"

if not LAMBDA:
	class MapperServicer(mapreduce_pb2_grpc.MapperServicer):
		def __init__(self, transferType, XDTconfig=None):
			self.transferType = transferType
			if transferType == S3:
				self.s3_client = boto3.resource(
					service_name='s3',
					region_name=os.getenv('AWS_REGION'),
					aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
					aws_secret_access_key=os.getenv('AWS_SECRET_KEY')
				)
			if transferType == XDT:
				if XDTconfig is None:
					log.fatal("Empty XDT config")
				self.XDTclient = XDTsrc.XDTclient(XDTconfig)
				self.XDTconfig = XDTconfig

		def put(self, bucket, key, obj, metadata=None):
			msg = "Mapper uploading object with key '" + key + "' to " + self.transferType
			log.info(msg)
			log.info("object is of type %s", type(obj))

			with tracing.Span(msg):
				if self.transferType == S3:
					s3object = self.s3_client.Object(bucket_name=bucket, key=key)
					if metadata is None:
						response = s3object.put(Body=obj)
					else:
						response = s3object.put(Body=obj, Metadata=metadata)
				elif self.transferType == XDT:
					key = self.XDTclient.Put(payload=obj)

			return key

		def get(self, bucket, key):
			msg = "Mapper gets key '" + key + "' from " + self.transferType
			log.info(msg)
			with tracing.Span(msg):
				if self.transferType == S3:
					obj = self.s3_client.Object(bucket_name=bucket, key=key)
					response = obj.get()
					return response['Body'].read()
				elif self.transferType == XDT:
					return XDTdst.Get(key, self.XDTconfig)

		def Map(self, request, context):

			mapArgs = {
				'srcBucket' : request.srcBucket,
				'destBucket' : request.destBucket,
				'jobId' 	: request.jobId,
				'mapperId'	: request.mapperId,
				'nReducers' : request.nReducers,
				'keys' 		: [grpc_key.key for grpc_key in request.keys],
				'getMethod' : self.get,
				'putMethod'	: self.put,
				'mapReply'	: mapreduce_pb2.MapReply
			}

			reply = MapFunction(mapArgs)
			response = reply['mapReply']

			for key in reply['keys']:
				grpc_keys = mapreduce_pb2.Keys()
				grpc_keys.key = key
				response.keys.append(grpc_keys)

			response.reply = "success"
			return response

if LAMBDA:
	class AWSLambdaMapperServicer:
		def __init__(self):
			self.s3_client = boto3.resource(service_name='s3')

		def put(self, bucket, key, obj, metadata=None):
			msg = "Mapper uploading object with key '" + key + "' to S3"
			log.info(msg)
			log.info("object is of type %s", type(obj))

			with tracing.Span(msg):
				s3object = self.s3_client.Object(bucket_name=bucket, key=key)
				if metadata is None:
					response = s3object.put(Body=obj)
				else:
					response = s3object.put(Body=obj, Metadata=metadata)

			return key

		def get(self, bucket, key):
			msg = "Mapper gets key '" + key + "' from S3"
			log.info(msg)

			with tracing.Span(msg):
				obj = self.s3_client.Object(bucket_name=bucket, key=key)
				response = obj.get()
				return response['Body'].read()

		def Map(self, event, context):

			mapArgs = {
				'srcBucket' : event["srcBucket"],
				'destBucket' : event["destBucket"],
				'jobId' 	: event["jobId"],
				'mapperId'	: event["mapperId"],
				'nReducers' : event["nReducers"],
				'keys' 		: event['keys'].split(','),
				'getMethod' : self.get,
				'putMethod'	: self.put,
				'mapReply'	: None
			}

			response = MapFunction(mapArgs)

			return {'keys' : response['keys'], 'reply' : 'success'}


def serve():
	transferType = os.getenv('TRANSFER_TYPE', S3)

	XDTconfig = dict()
	if transferType == XDT:
		XDTconfig = XDTutil.loadConfig()
		log.info("XDT config:")
		log.info(XDTconfig)

	log.info("Using inline or s3 transfers")
	max_workers = int(os.getenv("MAX_SERVER_THREADS", 16))
	server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
	mapreduce_pb2_grpc.add_MapperServicer_to_server(
		MapperServicer(transferType=transferType, XDTconfig=XDTconfig), server)
	server.add_insecure_port('[::]:' + args.sp)
	server.start()
	server.wait_for_termination()


def lambda_handler(event, context):
	mapperServicer = AWSLambdaMapperServicer()
	return mapperServicer.Map(event, context)

if __name__ == '__main__' and not LAMBDA:
	log.basicConfig(level=log.INFO)
	serve()
