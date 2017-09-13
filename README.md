# infra-ext-mysql5

[![N|Solid](https://www.whatap.io/img/logo.png)](https://www.whatap.io)

infra-ext-mysql5 is a mysql monitoring plugin for whatap-infra monitoring service.

  - Monitor Query, Connection, Memory, File usage
    
### Installation

    infra-ext-mysql5 requires [python](https://python.org/) 2.6+ to run.

    Install the dependencies and devDependencies and start the server.

    ```sh
    $ cd infra-ext-mysql5
    $ sudo pip install -r requirements.txt
    $ cd config
    $ sudo cp mysql.config.example {new file name}.config
    $ sudo vi mysql.config
    ```
    mysql.config
    ```
    name={mysql instance name}
    host={hostname or ip}
    port={port}
    username={username with REPLICATION CLIENT grant and above}
    password={password}                                            
    ```
    register script
    ```sh
    sudo WHATAP_HOME=/usr/whatap/infra/conf /usr/whatap/infra/whatap_infrad --user={user to execute mysql monitor} init-script
    ```
