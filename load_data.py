from database import import_csv_to_db

def load_test_data():
    import_csv_to_db('testdata.csv')

if __name__ == "__main__":
    load_test_data()