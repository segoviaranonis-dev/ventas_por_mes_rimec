import sys
for lib in ['playwright', 'selenium', 'pyppeteer', 'webdriver_manager']:
    try:
        __import__(lib)
        print(f"{lib}: INSTALLED")
    except ImportError:
        print(f"{lib}: NOT INSTALLED")
