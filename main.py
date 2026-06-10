# main.py
import api_manager
import excel_manager

def menu():
    while True:
        print("\n--- GOOGLE REVIEWS MANAGER ---")
        print("1. Pobierz informacje z Google (zapis do CSV)")
        print("2. Przenieś suche dane do Excel")
        print("3. Przenieś i wizualizuj dane w Excel (Wykres)")
        print("0. Wyjście")
        
        wybor = input("\nWybierz opcję: ")

        if wybor == '1':
            api_manager.pobierz_z_google()
        elif wybor == '2':
            excel_manager.przenies_do_excel(wizualizuj=False)
        elif wybor == '3':
            excel_manager.przenies_do_excel(wizualizuj=True)
        elif wybor == '0':
            print("Zamykanie programu...")
            break
        else:
            print("Nieprawidłowy wybór, spróbuj ponownie.")

if __name__ == "__main__":
    menu()