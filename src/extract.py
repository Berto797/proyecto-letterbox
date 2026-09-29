from pathlib import Path
import csv
import shutil

# Se obtiene el input_path de manera relativa a extract.py
def _get_csv_path():
    script_path = Path(__file__).resolve()
    project_path = script_path.parent.parent
    input_path = project_path/"data"/"input"
    return input_path

# Se obtiene lista de .csv en input_path
def _get_csv_files(input_path):
    csv_files = list(input_path.glob("*.csv"))
    return csv_files

# Se checkea que el num de .csv sea 1 y si es asi te devuelve el nombre del archivo .csv
def _get_single_csv(csv_files):
    if len(csv_files) == 0:
        raise FileNotFoundError("No se encontró ningún CSV")
    elif len(csv_files) > 1:
        raise ValueError(f"Se esperaba 1 archivo CSV y en la ruta hay {len(csv_files)}") 
    else:
        return csv_files[0]

# Extrae la información del .csv
def _extract_csv(csv_file):
    try:
        with open(csv_file, encoding='utf-8-sig', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            film_list = list(reader)
            return film_list
    except UnicodeDecodeError as e:
        raise ValueError(f"El archivo {csv_file} no está codificado en UTF-8") from e

def input_to_processed(csv_file, keep_original=False):
    if keep_original:
        print("codigo keep original")
    else:
        print("codigo mover original")
  
def extract():
    input_path = _get_csv_path()
    csv_files = _get_csv_files(input_path)
    csv_file = _get_single_csv(csv_files)
    films_list = _extract_csv(csv_file)
    return films_list
    
if __name__ == "__main__":
    try:
        films_list = extract()
        print(films_list)
        input_to_processed(keep_original=True)
    except (FileNotFoundError, ValueError) as e:
        print(e) 