### Building Executables
You can build Refurboard into a distributable format for easier deployment.

1. Ensure you are in the Poetry shell:
    ```sh
    poetry shell
    ```
2. Install the development dependencies:
    ```sh
    poetry install --with dev
    ```
3. Run the build script to create the executable:
    ```sh
    ./build_executable.sh
    ```