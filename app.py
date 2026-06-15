import streamlit as st
import pandas as pd
import tempfile
import io
from pathlib import Path
import sys

# Настройка страницы с широким контейнером
st.set_page_config(
    page_title="Алгоритмы обработки данных", 
    page_icon="🔧",
    layout="wide"  # 📌 Широкий режим
)

# Главная страница
def main_page():
    st.title("🔧 Выбор алгоритма обработки данных")
    st.write("Выберите один из доступных алгоритмов для работы:")
    
    algorithm = st.radio(
        "Выберите алгоритм:",
        ["Вращающаяся дверь (сжатие данных)", "Определение характеристик переходного процесса"],
        label_visibility="collapsed"
    )
    
    return algorithm

# Функция для загрузки файла и вывода названий страниц
def process_file_upload():
    st.subheader("📤 Загрузка файла")
    uploaded_file = st.file_uploader("Выберите файл (.xlsx):", type=["xlsx"])
    
    if uploaded_file is not None:
        file_name = uploaded_file.name
        
        try:
            excel_file = pd.ExcelFile(uploaded_file)
            sheet_names = excel_file.sheet_names
            
            st.success(f"✅ Файл успешно загружен: {file_name}")
            st.write(f"**Тип файла:** .xlsx")
            st.write(f"**Названия всех страниц:**")
            
            for i, sheet in enumerate(sheet_names, 1):
                st.write(f"{i}. {sheet}")
            
            excel_file.close()
            
            return uploaded_file, sheet_names
        except Exception as e:
            st.error(f"❌ Ошибка при чтении файла: {e}")
            return None, []
    
    return None, []

# Алгоритм 1: Вращающаяся дверь (сжатие данных)
def rotating_door_algorithm():
    st.title("🔄 Алгоритм «Вращающаяся дверь» (сжатие данных)")
    st.write("Этот алгоритм используется для сжатия данных в промышленных процессах.")
    st.write("Загрузите файл .xlsx для обработки.")
    
    uploaded_file, sheet_names = process_file_upload()
    
    if uploaded_file is not None and len(sheet_names) > 0:
        st.markdown("---")
        st.subheader("⚙️ Настройки алгоритма")
        
        if st.button("🚀 Запустить алгоритм сжатия"):
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                    tmp_path = tmp_file.name
                    tmp_file.write(uploaded_file.getvalue())
                
                sys.path.insert(0, str(Path(__file__).parent))
                
                from clean_swinging_door import algorithm
                
                # ЗАПУСК АЛГОРИТМА
                compressed_data, all_metrics = algorithm(tmp_path)
                
                st.success("✅ Алгоритм успешно выполнен!")
                
                # ──────────────────────────────────────────────
                # КРАСИВЫЙ ВЫВОД МЕТРИК ДЛЯ КАЖДОГО ПАРАМЕТРА
                # ──────────────────────────────────────────────
                
                # Самые важные метрики (без массивов)
                important_metrics = {
                    'MAE': 'MAE ( (погрешность)',
                    'R²': 'R² (коэф. детерминации)',
                    'Compression Ratio': 'Коэф. сжатия (x)',
                    'Compression %': 'Сжатие (%)',
                    'Points Original': 'Точек (ориг.)',
                    'Points Compressed': 'Точек (сжато)',
                    'Points Saved': 'Удалено точек',
                    'RMSE': 'RMSE',
                    'MAPE (%)': 'MAPE (%)',
                    'MASE': 'MASE',
                    'Max Error': 'Max Error'
                }
                
                for param_name, param_data in compressed_data.items():
                    st.markdown("---")
                    st.subheader(f"🔹 **{param_name}**")
                    
                    # Основная информация
                    st.info(f"📊 **Сохранено точек:** {len(param_data)}")
                    st.info(f"⏱️ **Временной диапазон:** {param_data['Время'].min()} → {param_data['Время'].max()}")
                    
                    # Таблица с метриками
                    if param_name in all_metrics:
                        metrics = all_metrics[param_name]
                        
                        display_data = {}
                        
                        for metric_key, metric_name in important_metrics.items():
                            if metric_key in metrics:
                                value = metrics[metric_key]
                                # Форматируем числа красиво
                                if isinstance(value, float):
                                    if metric_key in ['Compression %', 'MAPE (%)']:
                                        display_data[metric_name] = f"{value:.2f}%"
                                    elif metric_key in ['R²', 'MASE', 'MAE', 'RMSE', 'Max Error']:
                                        display_data[metric_name] = f"{value:.4f}"
                                    elif metric_key == 'Compression Ratio':
                                        display_data[metric_name] = f"{value:.2f}x"
                                    else:
                                        display_data[metric_name] = f"{value:.2f}"
                                else:
                                    display_data[metric_name] = value
                        
                        # Вывод как таблицу
                        df_metrics = pd.DataFrame([display_data])
                        st.dataframe(df_metrics, hide_index=True, use_container_width=True)
                        
                        # Блок с улучшением (коэф. сжатия)
                        if 'Compression Ratio' in metrics:
                            comp_ratio = metrics['Compression Ratio']
                            if comp_ratio > 3:
                                st.success(f"🎯 **Коэффициент сжатия: {comp_ratio:.2f}x** (отлично!)")
                            elif comp_ratio > 2:
                                st.info(f"👍 **Коэффициент сжатия: {comp_ratio:.2f}x** (хорошо)")
                            else:
                                st.warning(f"⚠️ **Коэффициент сжатия: {comp_ratio:.2f}x** (слабо)")
                        
                        # Блок с погрешностью
                        if 'MAE' in metrics and 'R²' in metrics:
                            mae = metrics['MAE']
                            r2 = metrics['R²']
                            if mae < 0.5 and r2 > 0.9:
                                st.success(f"✨ **Точность отличная:** MAE={mae:.4f}, R²={r2:.4f}")
                            elif mae < 1.0 and r2 > 0.8:
                                st.info(f"✓ **Точность хорошая:** MAE={mae:.4f}, R²={r2:.4f}")
                            else:
                                st.warning(f"⚠️ **Точность средняя:** MAE={mae:.4f}, R²={r2:.4f}")
                        
                # ──────────────────────────────────────────────
                # СВОДНАЯ ТАБЛИЦА ПО ВСЕМ ПАРАМЕТРАМ
                # ──────────────────────────────────────────────
                
                st.markdown("---")
                st.subheader("📊 Общая статистика сжатия")
                
                summary_data = []
                for param_name, param_data in compressed_data.items():
                    if param_name in all_metrics:
                        metrics = all_metrics[param_name]
                        summary_row = {
                            "Параметр": param_name,
                            "Оригин. точек": metrics.get('Points Original', 0),
                            "Сжато точек": metrics.get('Points Compressed', 0),
                            "Удалено": metrics.get('Points Saved', 0),
                            "Сжатие (%)": round(metrics.get('Compression %', 0), 2),
                            "Коэф. (x)": round(metrics.get('Compression Ratio', 0), 2),
                            "MAE": round(metrics.get('MAE', 0), 4),
                            "R²": round(metrics.get('R²', 0), 4),
                            "RMSE": round(metrics.get('RMSE', 0), 4)
                        }
                        summary_data.append(summary_row)
                
                df_summary = pd.DataFrame(summary_data)
                st.dataframe(df_summary, use_container_width=True, hide_index=True)
                
                # ──────────────────────────────────────────────
                # КНОПКА СКАЧАТЬ EXCEL
                # ──────────────────────────────────────────────
                
                st.markdown("---")
                st.subheader("💾 Скачивание результата")
                
                output_path = tmp_path + "_result.xlsx"
                
                # Копируем оригинал и добавляем лист с сжатыми данными
                with pd.ExcelFile(tmp_path) as xls_in:
                    with pd.ExcelWriter(output_path, engine='openpyxl') as xls_out:
                        for sheet in xls_in.sheet_names:
                            df = pd.read_excel(xls_in, sheet_name=sheet)
                            df.to_excel(xls_out, sheet_name=sheet, index=False)
                    
                    # Добавляем лист с сжатыми данными
                    dfs = []
                    for param in compressed_data.keys():
                        df = compressed_data[param][['Время', 'Значение']].reset_index(drop=True)
                        dfs.append(df)
                    
                    result_df = pd.concat(dfs, axis=1)
                    
                    with pd.ExcelFile(output_path) as xls_in:
                        with pd.ExcelWriter(output_path, mode='a', engine='openpyxl', if_sheet_exists='replace') as xls_out:
                            result_df.to_excel(xls_out, sheet_name="Сжатые данные", index=False)
                
                # Чит для скачивания
                with open(output_path, 'rb') as f:
                    excel_bytes = f.read()
                
                st.download_button(
                    label="📥 Скачать Excel с сжатыми данными",
                    data=excel_bytes,
                    file_name="compressed_data_result.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                # Очищаем временные файлы
                Path(tmp_path).unlink()
                Path(output_path).unlink()
                
            except ImportError as e:
                st.error(f"❌ Не удалось импортировать алгоритм: {e}")
                st.info("💡 Убедись, что файл clean_swinging_door.py находится в той же папке, как app.py")
            except Exception as e:
                st.error(f"❌Ошибка при выполнении алгоритма: {e}")
                st.exception(e)
    
    st.markdown("---")


# Алгоритм 2: Определение характеристик переходного процесса
def transient_process_algorithm():
    st.title("📈 Алгоритм «Определение характеристик переходного процесса»")
    st.write("Этот алгоритм используется для анализа переходных процессов в автоматизированных системах.")
    
    uploaded_file, sheet_names = process_file_upload()
    
    if uploaded_file is not None and len(sheet_names) > 0:
        st.markdown("---")
        st.subheader("⚙️ Настройки алгоритма")
        
        sheet_choice = st.selectbox("Выберите страницу из файла:", sheet_names)
        
        if st.button("🚀 Запустить алгоритм"):
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                    tmp_path = tmp_file.name
                    tmp_file.write(uploaded_file.getvalue())
                
                current_dir = Path(__file__).parent
                sys.path.insert(0, str(current_dir))
                
                from clean_analyze import algorithm, read_and_process_file2, analyze_delay_and_maxima
                
                result = algorithm(tmp_path, sheet_choice)
                
                st.success("✅ Алгоритм успешно выполнен!")
                
                # Очищаем временный файл
                Path(tmp_path).unlink()
                
                # ──────────────────────────────────────────────
                # КРАСИВЫЙ ВЫВОД РЕЗУЛЬТАТОВ
                # ──────────────────────────────────────────────
                
                # Параметры, которые будем показывать (без массивов)
                important_params = {
                    "delay": "Задержка (с)",
                    "delay_hours": "Задержка (ч)",
                    "original_mae": "Original MAE",
                    "shifted_mae": "Shifted MAE",
                    "improvement": "Улучшение (%)",
                    "mean_maxima": "Амплитуда колебаний (м3)",
                    # "median_maxima": "Мед. максимумы",
                    "maxima_ratio": "Скорость регулирования (м3/ч)",
                    # "lower_bound": "Нижняя граница",
                    # "upper_bound": "Верхняя граница",
                    # "n_peaks_total": "Всго пиков",
                    # "n_peaks_filtered": "Фильтр. пиков",
                    # "n_removed_lower": "Удал. (ниж.)",
                    # "n_removed_upper": "Удал. (верх.)"
                }
                
                # Вывод для каждого датчика
                for sensor_name, sensor_data in result.items():
                    st.markdown("---")
                    st.subheader(f"🔹 **{sensor_name}**")
                    
                    # Создаём таблицу с важными параметрами
                    display_data = {}
                    
                    for param_key, param_name in important_params.items():
                        if param_key in sensor_data:
                            value = sensor_data[param_key]
                            # Форматируем числа красиво
                            if isinstance(value, float):
                                if param_key in ["delay_hours", "mean_maxima", "median_maxima", 
                                                 "maxima_ratio", "lower_bound", "upper_bound"]:
                                    display_data[param_name] = f"{value:.4f}"
                                elif param_key == "improvement":
                                    display_data[param_name] = f"{value:.2f}%"
                                else:
                                    display_data[param_name] = f"{value:.4f}"
                            else:
                                display_data[param_name] = value
                    
                    # Вывод как таблицу
                    df_display = pd.DataFrame([display_data])
                    st.dataframe(df_display, hide_index=True, use_container_width=True)
                    
                    # Блок с улучшением (выделяем цветом)
                    if "improvement" in sensor_data:
                        improvement = sensor_data["improvement"]
                        if improvement > 40:
                            st.success(f"🎯 **Улучшение MAE: {improvement:.2f}%**")
                        elif improvement > 20:
                            st.info(f"👍 **Улучшение MAE: {improvement:.2f}%**")
                        else:
                            st.warning(f"⚠️ **Улучшение MAE: {improvement:.2f}%**")
                    
                    # Блок с задержкой
                    if "delay_hours" in sensor_data:
                        st.info(f"⏱️ **Задержка: {sensor_data['delay']} с ({sensor_data['delay_hours']:.3f} ч)**")
                
                # Общий вывод по всем датчикам
                st.markdown("---")
                st.subheader("📊 Общая статистика")
                
                # Создаём сводную таблицу
                summary_data = []
                for sensor_name, sensor_data in result.items():
                    summary_row = {
                        "Датчик": sensor_name,
                        "Задержка (с)": sensor_data.get("delay_hours", 0),
                        "Улучшение (%)": round(sensor_data.get("improvement", 0), 2),
                        "Original MAE": round(sensor_data.get("original_mae", 0), 4),
                        "Shifted MAE": round(sensor_data.get("shifted_mae", 0), 4),
                        "Амплитуда колебаний (м3)": round(sensor_data.get("mean_maxima", 0), 4),
                        "Скорость регулирования (м3/ч)": round(sensor_data.get("maxima_ratio", 0), 4),
                    }
                    summary_data.append(summary_row)
                
                df_summary = pd.DataFrame(summary_data)
                st.dataframe(df_summary, use_container_width=True, hide_index=True)
                
                # Melhor improvement
                # if len(summary_data) > 0:
                #     best = df_summary.loc[df_summary["Улучшение (%)"].max()]
                #     st.success(f"🏆 **Лучший датчик:** {best['Датчик']} с улучшением {best['Улучшение (%)']}%")
                
            except ImportError as e:
                st.error(f"❌ Не удалось импортировать алгоритм из clean_analyze.py: {e}")
                st.info("💡 Убедись, что файл clean_analyze.py находится в той же папке, как app.py")
            except Exception as e:
                st.error(f"❌Ошибка при выполнении алгоритма: {e}")
    
    st.markdown("---")

# Главная функция
def main():
    algorithm = main_page()
    
    st.markdown("---")
    
    if algorithm == "Вращающаяся дверь (сжатие данных)":
        rotating_door_algorithm()
    elif algorithm == "Определение характеристик переходного процесса":
        transient_process_algorithm()

if __name__ == "__main__":
    main()