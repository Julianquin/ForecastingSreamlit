import streamlit as st
import pandas as pd
from prophet import Prophet
import chardet
import plotly.graph_objs as go

# Título de la aplicación
st.title("Herramienta de Forecasting Mejorada")

# Cargar el CSV
uploaded_file = st.file_uploader("Carga tu archivo CSV", type=["csv"])

df_global = None

if uploaded_file is not None:
    # Detectar la codificación del archivo
    raw_data = uploaded_file.read()
    result = chardet.detect(raw_data)
    encoding = result['encoding']

    # Volver al inicio del archivo después de la detección
    uploaded_file.seek(0)

    # Opciones para el usuario
    st.sidebar.header("Opciones de Lectura del CSV")
    delimiter = st.sidebar.text_input("Delimitador de columnas", value=',', help="Ejemplo: ',' o ';'")
    decimal_sep = st.sidebar.text_input("Separador de decimales", value='.', help="Ejemplo: '.' o ','")
    date_format = st.sidebar.radio("Formato de Fecha", ('dd/mm/aaaa', 'mm/dd/aaaa', 'aaaa-mm-dd'))

    # Configurar el parámetro dayfirst basado en la selección del usuario
    dayfirst = True if date_format == 'dd/mm/aaaa' else False

    # Leer el archivo con el encoding detectado y las opciones del usuario
    uploaded_file.seek(0)  # Volver al inicio del archivo
    try:
        df = pd.read_csv(uploaded_file, encoding=encoding, sep=delimiter, engine='python', decimal=decimal_sep, parse_dates=True, dayfirst=dayfirst)
    except Exception as e:
        st.error(f"Error al leer el archivo CSV: {e}")
    else:
        st.write("Vista previa de los datos:")
        st.write(df.tail())

        # Ordenar por la columna de fecha
        date_column_candidates = [col for col in df.columns if df[col].dtype == 'datetime64[ns]']
        if len(date_column_candidates) > 0:
            df = df.sort_values(by=date_column_candidates[0])

        # Selección de columnas
        date_column = st.selectbox("Selecciona la columna de fecha", df.columns)
        target_column = st.selectbox("Selecciona la columna objetivo (target)", df.columns)

        # Limpiar la columna objetivo
        df[target_column] = df[target_column].replace({r'[^\d.]': ''}, regex=True).replace('', pd.NA).astype(float)
        df.dropna(subset=[target_column], inplace=True)

        # Selección del número de períodos a predecir
        periods_to_predict = st.number_input("Número de períodos a predecir", min_value=1, max_value=365, value=150)

        # Selección del intervalo de frecuencia
        freq_options = ['D', 'M', 'Y']
        freq_map = {'D': 'diario', 'M': 'mensual', 'Y': 'anual'}
        freq = st.selectbox("Selecciona la frecuencia de los datos", freq_options, format_func=lambda x: freq_map[x])

        if st.button("Entrenar el modelo"):
            try:
                # Resetear el DataFrame global para permitir nuevos entrenamientos
                df_global = None
                df = df.rename(columns={date_column: 'ds', target_column: 'y'})
                df['ds'] = pd.to_datetime(df['ds'], errors='coerce')
                df['y'] = df['y'].replace({r',': ''}, regex=True).replace('?', pd.NA).astype(float)  # Convertir 'y' a numérico después de eliminar separadores de miles y manejar caracteres no convertibles
                df = df.sort_values(by='ds')
                df.dropna(subset=['ds', 'y'], inplace=True)

                model = Prophet()
                model.fit(df)

                # Predecir los próximos períodos especificados por el usuario
                future = model.make_future_dataframe(periods=periods_to_predict, freq=freq)
                forecast = model.predict(future)

                st.write(f"Predicción de los próximos {periods_to_predict} períodos ({freq_map[freq]}):")
                st.write(forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']])

                # Visualización del forecast con bandas de incertidumbre y valores reales
                fig = go.Figure()

                # Determinar el rango de visualización (últimos 4x períodos de predicción)
                start_date = df['ds'].iloc[-(4 * periods_to_predict)] if len(df) >= 4 * periods_to_predict else df['ds'].iloc[0]

                # Agregar los valores reales
                df_plot = df[df['ds'] >= start_date]
                fig.add_trace(go.Scatter(
                    x=df_plot['ds'],
                    y=df_plot['y'],
                    mode='lines',
                    name='Valores reales',
                    line=dict(color='green')
                ))

                # Agregar la predicción solo para los períodos futuros
                future_forecast = forecast[forecast['ds'] > df['ds'].max()]
                fig.add_trace(go.Scatter(
                    x=future_forecast['ds'],
                    y=future_forecast['yhat'],
                    mode='lines',
                    name='Predicción',
                    line=dict(color='blue')
                ))

                # Agregar bandas de incertidumbre solo para los períodos futuros
                fig.add_trace(go.Scatter(
                    x=future_forecast['ds'],
                    y=future_forecast['yhat_upper'],
                    mode='lines',
                    name='Límite superior',
                    line=dict(color='lightblue'),
                    fill=None
                ))
                fig.add_trace(go.Scatter(
                    x=future_forecast['ds'],
                    y=future_forecast['yhat_lower'],
                    mode='lines',
                    name='Límite inferior',
                    line=dict(color='lightblue'),
                    fill='tonexty'
                ))

                fig.update_layout(
                    title='Forecast vs Time',
                    xaxis_title='Fecha',
                    yaxis_title='Forecast',
                    template='plotly_white'
                )

                st.plotly_chart(fig)
            except Exception as e:
                st.error(f"Error durante el entrenamiento del modelo: {e}")
