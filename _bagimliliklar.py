"""
Sadece Robi.exe derlemesi için: Robi'nin kod dosyaları exe'ye gömülmediği (güncellenebilsinler diye)
için PyInstaller onların kullandığı kütüphaneleri göremez. Bu liste onları exe'ye dahil ettirir.
Fonksiyon hiç çağrılmaz. Derlemeden önce araclar/bagimlilik_uret.py ile otomatik üretilir.
"""


def _liste():
    import PIL  # noqa
    import PIL.ImageDraw  # noqa
    import PIL.ImageGrab  # noqa
    import base64  # noqa
    import concurrent.futures  # noqa
    import ctypes  # noqa
    import ctypes.wintypes  # noqa
    import datetime  # noqa
    import ddgs  # noqa
    import docx  # noqa
    import docx.oxml  # noqa
    import docx.oxml.ns  # noqa
    import docx.shared  # noqa
    import encodings.idna  # noqa
    import glob  # noqa
    import html  # noqa
    import html.parser  # noqa
    import importlib  # noqa
    import io  # noqa
    import json  # noqa
    import lxml.etree  # noqa
    import os  # noqa
    import pathlib  # noqa
    import psutil  # noqa
    import random  # noqa
    import re  # noqa
    import requests  # noqa
    import send2trash  # noqa
    import shutil  # noqa
    import socket  # noqa
    import subprocess  # noqa
    import sys  # noqa
    import threading  # noqa
    import time  # noqa
    import traceback  # noqa
    import urllib.parse  # noqa
    import uuid  # noqa
    import webbrowser  # noqa
    import webview  # noqa
    import webview.platforms.edgechromium  # noqa
    import webview.platforms.winforms  # noqa
    import zipfile  # noqa
