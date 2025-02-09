module github.com/vhive-serverless/vSwarm/tools/deployer

go 1.21

replace github.com/vhive-serverless/vSwarm/tools/endpoint => ../endpoint

require (
	github.com/sirupsen/logrus v1.9.3
	github.com/vhive-serverless/vSwarm/tools/endpoint v0.0.0-20231002141623-fe250ed33dde
)

require golang.org/x/sys v0.30.0 // indirect
