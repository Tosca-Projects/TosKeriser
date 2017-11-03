

# SockShop

> **SockShop** is a microservices demo application that simulates an e-commerce website that sells socks.

`Sockshop` is intended to aid the demonstration and testing of microservice and cloud native technologies.

  - [SockeShop site](https://microservices-demo.github.io/)
  - [Github repo](https://github.com/microservices-demo)

### SockShop Architecture
The architecture is composed by nine microservices (plus the `edge-router` between the User and the Front End).
The figure below shows the microservices composing the architecture.

<div style="text-align:center">
  <img src="docs/img/Architecture.png" alt="Drawing" style="width: 400px" />
</div>


Each microservice is in charge to control a single functionality of the application:
- `Front End`: is the front end of the application.
- `Order`: manages the orders.
- `Payment`: manages the payments.
- `User`: manages the list of the users and their information.
- `Catalogue`: manages the  socks stored in the catalogue.
- `Cart`: manages the cart of an user.
- `Shipping`: manages the shipping procedure of an order.
- `Queue`: enqueues the orders in a queue.
- `Queue Master`: processes the orders queue. It spawns new docker containers (`weaveworksdemos/worker`) that simulate the shipping process.


Main characteristic of the `SockShop` application:
 - _Microservice-based application_: it is designed to have as much as possible microservices  communicate using REST over HTTP.
 - _Polyglot_: it exploits different technologies and programming languages (_Java_, _go_,_NodeJs_, _RabbitMq_)



 ## Additional features
 `SockShop` is equipped also with a `Locust.io` load testing, a `Zipkin` tracing.


 #### Locust

 `git clone https://github.com/microservices-demo/load-test.git`

 `cd \load-test`

 `pip install locustio`

 Load-test with locust.py (and web interface):

 `locust --host=http://127.0.0.1 -f  locustfile.py `

 Got to `http://127.0.0.1:8089/` insert the number of users and the hatch rate(The rate per second in which clients are spawned.).


 Load-test  with locust Locust:
 ```Usage:
   runLocust.sh [ http://hostname/ ] OPTIONS

 Options:
   -d  Delay before starting
   -h  Target host url, e.g. http://localhost/
   -c  Number of clients (default 2)
   -r  Number of requests (default 10)

 Description:
   Runs a Locust load simulation against specified host.
 ```

 `./runLocust.sh  -d 60 -r 200 -c 2 -h edge-router" `


 Load-test on Docker with Locust

 `docker build -t load-test .`

 `docker run --network dockercompose_default  load-test -h edge-router -c 2 -r 200 `


 ####  Zipkin

  'http://127.0.0.1:9411'


<!-- ## front-end

`front-end` default [endpoints](https://github.com/microservices-demo/front-end/blob/master/api/endpoints.js)

```
module.exports = {
    catalogueUrl:  util.format("http://catalogue%s", domain),
    tagsUrl:       util.format("http://catalogue%s/tags", domain),
    cartsUrl:      util.format("http://carts%s/carts", domain),
    ordersUrl:     util.format("http://orders%s", domain),
    customersUrl:  util.format("http://user%s/customers", domain),
    addressUrl:    util.format("http://user%s/addresses", domain),
    cardsUrl:      util.format("http://user%s/cards", domain),
    loginUrl:      util.format("http://user%s/login", domain),
    registerUrl:   util.format("http://user%s/register", domain),
};
```


## user

``` $ /user -h
Usage of /user:
  -database string
    	Database to use, Mongodb or ... (default "mongodb")
  -link-domain string
    	HATEAOS link domain (default "user")
  -mongo-host string
    	Mongo host (default "user-db")
  -mongo-password string
    	Mongo password
  -mongo-user string
    	Mongo user
  -port string
    	Port on which to run (default "8084")
  -zipkin string
    	Zipkin address
```

## orders

`java.sh` script launched inside the `weaveworksdemos/msd-java:8u131` for running the `orders` Software.

``` /usr/local/bin # cat java.sh
#!/bin/sh

if [ -z "$JAVA_OPTS" ]; then
  JAVA_OPTS="-XX:+UnlockExperimentalVMOptions -XX:+UseCGroupMemoryLimitForHeap -XX:MaxRAMFraction=1 -XX:UseG1GC"
fi
```

API.
- GET http://0.0.0.0:8082/health : return a json

## payment

`Payments`  microservice help.

```root@a76dbadda182:/go/src/github.com/microservices-demo/payment# /app/main -h
    Usage of /app/main:
      -decline float
        	Decline payments over certain amount (default 100)
      -port string
        	Port to bind HTTP listener (default "8080")
      -zipkin string
        	Zipkin address -->
```
