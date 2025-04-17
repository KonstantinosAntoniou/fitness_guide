import pandas as pd
import os
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

class Food:
    def __init__(self, name=None, label=None, measurement=None, calories = None, protein=None, carbs=None, fat_saturated=None, fat_regular=None, sodium=None):
        self.name = name
        self.label = label
        self.measurement = measurement
        self.calories = calories
        self.protein = protein
        self.carbs = carbs
        self.fat_saturated = fat_saturated
        self.fat_regular = fat_regular
        self.sodium = sodium

        # The Excel file where food data is stored
        self.excel_file = 'foods_log.xlsx'
        
        # Ensure the file exists with the proper columns
        if not os.path.exists(self.excel_file):
            self.create_excel_file()

    def create_excel_file(self):
        columns = ['Name', 'Label', 'Measurement', 'Calories', 'Protein', 'Carbs', 'Fat_Saturated', 'Fat_Regular', 'Sodium']
        df = pd.DataFrame(columns=columns)
        df.to_excel(self.excel_file, index=False)

    def log_food(self):
        df = pd.read_excel(self.excel_file)
        if not ((df['Name'].str.lower() == self.name.lower()) & (df['Label'].str.lower() == self.label.lower())).any():
            new_food = {
                'Name': self.name,
                'Label': self.label,
                'Measurement': self.measurement,
                'Calories' : self.calories,
                'Protein': self.protein,
                'Carbs': self.carbs,
                'Fat_Saturated': self.fat_saturated,
                'Fat_Regular': self.fat_regular,
                'Sodium': self.sodium
            }
            df = df._append(new_food, ignore_index=True)
            df.to_excel(self.excel_file, index=False)
            return f"{self.name} ({self.label}) logged successfully!"
        else:
            return f"{self.name} ({self.label}) is already logged."

    def print_all_foods(self):
        df = pd.read_excel(self.excel_file)
        print(df)

    def get_length(self):
        df = pd.read_excel(self.excel_file)
        return len(df)

    def print_names_labels(self):
        df = pd.read_excel(self.excel_file)
        for index, row in df.iterrows():
            print(f"Name: {row['Name']}, Label: {row['Label']}")