from a2ln import main

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\r', end='')
        exit()
