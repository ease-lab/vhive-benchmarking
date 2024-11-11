// MIT License

// Copyright (c) 2022 EASE lab

// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:

// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.

// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

module github.com/vhive-serverless/vSwarm/benchmarks/hotel-app

go 1.21
toolchain go1.22.9

replace github.com/vhive-serverless/vSwarm/utils/tracing/go => ../../utils/tracing/go

require (
	github.com/bradfitz/gomemcache v0.0.0-20230905024940-24af94b03874
	github.com/hailocab/go-geoindex v0.0.0-20160127134810-64631bfe9711
	github.com/sirupsen/logrus v1.9.3
	github.com/vhive-serverless/vSwarm-proto v0.5.0
	github.com/vhive-serverless/vSwarm/utils/tracing/go v0.0.0-20240422181019-5b1711d87c5d
	go.mongodb.org/mongo-driver v1.16.0
	golang.org/x/net v0.29.0
	google.golang.org/grpc v1.68.0
	gopkg.in/mgo.v2 v2.0.0-20190816093944-a6b53ec6cb22
)

require (
	github.com/go-logr/logr v1.4.2 // indirect
	github.com/go-logr/stdr v1.2.2 // indirect
	github.com/golang/snappy v0.0.4 // indirect
	github.com/google/uuid v1.6.0 // indirect
	github.com/klauspost/compress v1.17.8 // indirect
	github.com/montanaflynn/stats v0.7.1 // indirect
	github.com/openzipkin/zipkin-go v0.4.3 // indirect
	github.com/xdg-go/pbkdf2 v1.0.0 // indirect
	github.com/xdg-go/scram v1.1.2 // indirect
	github.com/xdg-go/stringprep v1.0.4 // indirect
	github.com/youmark/pkcs8 v0.0.0-20201027041543-1326539a0a0a // indirect
	go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc v0.53.0 // indirect
	go.opentelemetry.io/otel v1.28.0 // indirect
	go.opentelemetry.io/otel/exporters/zipkin v1.28.0 // indirect
	go.opentelemetry.io/otel/metric v1.28.0 // indirect
	go.opentelemetry.io/otel/sdk v1.28.0 // indirect
	go.opentelemetry.io/otel/trace v1.28.0 // indirect
	golang.org/x/crypto v0.27.0 // indirect
	golang.org/x/sync v0.8.0 // indirect
	golang.org/x/sys v0.25.0 // indirect
	golang.org/x/text v0.18.0 // indirect
	google.golang.org/genproto/googleapis/rpc v0.0.0-20240903143218-8af14fe29dc1 // indirect
	google.golang.org/protobuf v1.34.2 // indirect
	gopkg.in/yaml.v2 v2.4.0 // indirect
)
