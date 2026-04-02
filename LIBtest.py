import pandas as pd
import openpyxl
import xlwings as xw
from pydantic import BaseModel

print("Pandas version:", pd.__version__)
print("OpenPyXL version:", openpyxl.__version__)
print("xlwings version:", xw.__version__)
print("Pydantic version:", BaseModel.__module__)
print("Библиотеки готовы к работе!")