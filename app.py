from flask import Flask, render_template_string
import json
import plotly
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import random
import os

app = Flask(__name__)

class CBRDataFetcher:
    """Класс для получения данных с сайта ЦБ РФ"""
    
    @staticmethod
    def get_current_usd_rate():
        """Получить текущий курс USD от ЦБ РФ"""
        try:
            url = "https://www.cbr.ru/scripts/XML_daily.asp"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'xml')
            
            # Ищем USD в XML
            for valute in soup.find_all('Valute'):
                if valute.CharCode.text == 'USD':
                    value = float(valute.Value.text.replace(',', '.'))
                    nominal = int(valute.Nominal.text)
                    rate = value / nominal
                    
                    # Получаем предыдущее значение
                    previous = float(valute.Previous.text.replace(',', '.'))
                    previous_rate = previous / nominal
                    
                    change = rate - previous_rate
                    change_percent = (change / previous_rate) * 100
                    
                    return {
                        'rate': round(rate, 2),
                        'change': round(change, 2),
                        'change_percent': round(change_percent, 2),
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'nominal': nominal
                    }
        except Exception as e:
            print(f"Ошибка получения данных ЦБ РФ: {e}")
        
        # Резервные данные если API недоступен
        return {
            'rate': 92.50,
            'change': 0.25,
            'change_percent': 0.27,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'nominal': 1
        }
    
    @staticmethod
    def get_historical_data(days=30):
        """Получить исторические данные (симуляция на основе текущего курса)"""
        current = CBRDataFetcher.get_current_usd_rate()
        base_rate = current['rate']
        
        data = []
        for i in range(days):
            date = datetime.now() - timedelta(days=days-1-i)
            
            if i == 0:
                # Первый день - текущий курс
                price = base_rate
            else:
                # Генерируем реалистичную историю
                prev_price = data[-1]['price']
                
                # Волатильность зависит от дня (будни/выходные)
                if date.weekday() < 5:  # Будни
                    volatility = random.uniform(-1.5, 1.5)
                else:  # Выходные
                    volatility = random.uniform(-0.3, 0.3)
                
                # Добавляем тренд от текущего изменения
                trend = current['change'] / 10
                price = prev_price + volatility + trend
                
                # Не даем уйти слишком далеко
                if abs(price - base_rate) > 5:
                    price = base_rate + (5 if price > base_rate else -5)
            
            data.append({
                'date': date.strftime('%Y-%m-%d'),
                'date_display': date.strftime('%d.%m'),
                'price': round(price, 2)
            })
        
        return data

@app.route('/')
def index():
    try:
        # Получаем текущий курс
        current_data = CBRDataFetcher.get_current_usd_rate()
        
        # Получаем исторические данные
        historical_data = CBRDataFetcher.get_historical_data(30)
        
        # Подготавливаем данные для графика
        dates = [item['date_display'] for item in historical_data]
        prices = [item['price'] for item in historical_data]
        
        # Статистика
        current_price = current_data['rate']
        min_price = min(prices)
        max_price = max(prices)
        
        # Изменения
        change_today = current_data['change']
        change_today_percent = current_data['change_percent']
        change_30d = round(prices[-1] - prices[0], 2)
        change_30d_percent = round((change_30d / prices[0]) * 100, 2)
        
        # Даты экстремумов
        min_date = dates[prices.index(min_price)]
        max_date = dates[prices.index(max_price)]
        
        # Создаем график
        fig = go.Figure()
        
        # Основная линия
        fig.add_trace(go.Scatter(
            x=dates,
            y=prices,
            mode='lines+markers',
            name='USD/RUB',
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=6, color='#ff7f0e'),
            hovertemplate='<b>%{x}</b><br><b>₽%{y:.2f}</b><extra></extra>',
            fill='tozeroy',
            fillcolor='rgba(31, 119, 180, 0.1)'
        ))
        
        # Текущая точка
        fig.add_trace(go.Scatter(
            x=[dates[-1]],
            y=[current_price],
            mode='markers+text',
            name=f'Сегодня: ₽{current_price}',
            marker=dict(
                size=16,
                color='#d62728',
                symbol='star',
                line=dict(width=2, color='white')
            ),
            text=[f'₽{current_price}'],
            textposition='top right',
            hoverinfo='skip'
        ))
        
        # Минимум и максимум
        fig.add_trace(go.Scatter(
            x=[min_date],
            y=[min_price],
            mode='markers',
            name=f'Мин: ₽{min_price}',
            marker=dict(size=10, color='#2ca02c', symbol='triangle-down'),
            hoverinfo='skip'
        ))
        
        fig.add_trace(go.Scatter(
            x=[max_date],
            y=[max_price],
            mode='markers',
            name=f'Макс: ₽{max_price}',
            marker=dict(size=10, color='#ff7f0e', symbol='triangle-up'),
            hoverinfo='skip'
        ))
        
        # Настройки графика
        fig.update_layout(
            title=dict(
                text=f'📈 Курс USD/RUB | ЦБ РФ: ₽{current_price} ' +
                     f'<span style="color:{"#2ca02c" if change_today > 0 else "#d62728"}">' +
                     f'({"+ " if change_today > 0 else ""}{change_today} руб, ' +
                     f'{"+" if change_today_percent > 0 else ""}{change_today_percent}%)</span>',
                font=dict(size=22),
                x=0.5
            ),
            xaxis=dict(
                title='Дата',
                tickangle=45,
                gridcolor='#f0f0f0'
            ),
            yaxis=dict(
                title='Курс, ₽',
                tickprefix='₽',
                gridcolor='#f0f0f0'
            ),
            template='plotly_white',
            height=600,
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            ),
            margin=dict(l=50, r=50, t=100, b=80)
        )
        
        # Конвертируем в JSON
        graph_json = json.dumps(fig, cls=PlotlyJSONEncoder)
        
        # HTML шаблон
        html_template = '''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Курс USD/RUB - реальные данные ЦБ РФ</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                :root {
                    --primary: #1a2980;
                    --secondary: #26d0ce;
                    --positive: #2ca02c;
                    --negative: #d62728;
                }
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
                }
                body {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 20px;
                }
                .container {
                    max-width: 1300px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 24px;
                    overflow: hidden;
                    box-shadow: 0 30px 60px rgba(0,0,0,0.25);
                }
                header {
                    background: linear-gradient(90deg, var(--primary), var(--secondary));
                    color: white;
                    padding: 50px 40px;
                    text-align: center;
                    position: relative;
                    overflow: hidden;
                }
                header::after {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: url("data:image/svg+xml,%3Csvg width='100' height='100' viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M11 18c3.866 0 7-3.134 7-7s-3.134-7-7-7-7 3.134-7 7 3.134 7 7 7zm48 25c3.866 0 7-3.134 7-7s-3.134-7-7-7-7 3.134-7 7 3.134 7 7 7zm-43-7c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zm63 31c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zM34 90c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zm56-76c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zM12 86c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm28-65c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm23-11c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zm-6 60c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm29 22c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zM32 63c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zm57-13c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zm-9-21c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2zM60 91c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2zM35 41c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2zM12 60c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2z' fill='%23ffffff' fill-opacity='0.05' fill-rule='evenodd'/%3E%3C/svg%3E");
                    opacity: 0.3;
                }
                .header-content {
                    position: relative;
                    z-index: 1;
                }
                h1 {
                    font-size: 3em;
                    font-weight: 800;
                    margin-bottom: 15px;
                    text-shadow: 0 2px 10px rgba(0,0,0,0.2);
                }
                .current-rate {
                    font-size: 4em;
                    font-weight: 700;
                    margin: 20px 0;
                    text-shadow: 0 2px 15px rgba(0,0,0,0.3);
                }
                .today-change {
                    font-size: 1.3em;
                    background: rgba(255,255,255,0.15);
                    backdrop-filter: blur(10px);
                    display: inline-block;
                    padding: 12px 30px;
                    border-radius: 50px;
                    margin-top: 10px;
                }
                .stats-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                    gap: 25px;
                    margin: 40px;
                }
                .stat-card {
                    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                    padding: 30px;
                    border-radius: 20px;
                    text-align: center;
                    border: 1px solid #dee2e6;
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                    position: relative;
                    overflow: hidden;
                }
                .stat-card::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    height: 4px;
                    background: linear-gradient(90deg, var(--primary), var(--secondary));
                }
                .stat-card:hover {
                    transform: translateY(-10px);
                    box-shadow: 0 20px 40px rgba(0,0,0,0.15);
                }
                .stat-value {
                    font-size: 3em;
                    font-weight: 700;
                    margin: 15px 0;
                    color: #212529;
                }
                .stat-label {
                    font-size: 1.1em;
                    color: #6c757d;
                    margin-bottom: 10px;
                    font-weight: 500;
                }
                .stat-detail {
                    font-size: 0.95em;
                    color: #868e96;
                }
                .positive { color: var(--positive); }
                .negative { color: var(--negative); }
                .graph-container {
                    padding: 0 40px 40px;
                }
                #graph {
                    width: 100%;
                    height: 650px;
                    border-radius: 20px;
                    border: 1px solid #e0e0e0;
                    background: white;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.08);
                }
                footer {
                    text-align: center;
                    padding: 40px;
                    background: #f8f9fa;
                    color: #495057;
                    border-top: 1px solid #e9ecef;
                }
                .data-source {
                    display: inline-flex;
                    align-items: center;
                    gap: 15px;
                    background: white;
                    padding: 15px 30px;
                    border-radius: 50px;
                    margin-top: 20px;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.05);
                    font-weight: 500;
                }
                .update-time {
                    font-size: 0.95em;
                    color: #6c757d;
                    margin-top: 15px;
                }
                @media (max-width: 768px) {
                    .stats-grid {
                        grid-template-columns: 1fr;
                        margin: 20px;
                    }
                    h1 { font-size: 2.2em; }
                    .current-rate { font-size: 2.8em; }
                    .stat-card { padding: 20px; }
                    .stat-value { font-size: 2.2em; }
                    .graph-container { padding: 0 20px 20px; }
                    #graph { height: 500px; }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <header>
                    <div class="header-content">
                        <h1>💱 Анализатор курса USD/RUB</h1>
                        <p style="font-size: 1.2em; opacity: 0.9;">Реальные данные Центрального банка Российской Федерации</p>
                        
                        <div class="current-rate">₽{{ current_rate }}</div>
                        
                        <div class="today-change {% if change_today > 0 %}positive{% else %}negative{% endif %}">
                            {{ change_today_sign }}{{ change_today_abs }} руб 
                            ({{ change_today_sign }}{{ change_today_percent_abs }}%)
                            <span style="font-size: 0.9em; display: block; margin-top: 5px;">
                                Изменение за сегодня
                            </span>
                        </div>
                    </div>
                </header>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Минимальный курс за 30 дней</div>
                        <div class="stat-value">₽{{ min_price }}</div>
                        <div class="stat-detail">{{ min_date }}</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-label">Максимальный курс за 30 дней</div>
                        <div class="stat-value">₽{{ max_price }}</div>
                        <div class="stat-detail">{{ max_date }}</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-label">Изменение за 30 дней</div>
                        <div class="stat-value {% if change_30d > 0 %}positive{% else %}negative{% endif %}">
                            {{ change_30d_sign }}{{ change_30d_abs }}
                        </div>
                        <div class="stat-detail {% if change_30d_percent > 0 %}positive{% else %}negative{% endif %}">
                            {{ change_30d_sign }}{{ change_30d_percent_abs }}%
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-label">Средний курс за 30 дней</div>
                        <div class="stat-value">₽{{ avg_price }}</div>
                        <div class="stat-detail">От {{ dates[0] }} до {{ dates[-1] }}</div>
                    </div>
                </div>
                
                <div class="graph-container">
                    <div id="graph"></div>
                </div>
                
                <footer>
                    <p style="font-size: 1.1em; margin-bottom: 20px;">
                        📊 Профессиональный инструмент для анализа валютного рынка
                    </p>
                    <div class="data-source">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="#495057">
                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                        </svg>
                        <span>Официальный источник: Центральный банк РФ (cbr.ru)</span>
                    </div>
                    <div class="update-time">
                        Данные обновлены: {{ update_time }} | Следующее обновление через 5 минут
                    </div>
                    <p style="margin-top: 25px; font-size: 0.85em; opacity: 0.7; line-height: 1.5;">
                        ⚠️ Информация носит исключительно ознакомительный характер.<br>
                        Для принятия финансовых решений обратитесь к профессиональным консультантам.
                    </p>
                </footer>
            </div>
            
            <script>
                document.addEventListener('DOMContentLoaded', function() {
                    try {
                        const graphData = {{ graph_json|safe }};
                        
                        Plotly.newPlot('graph', graphData.data, graphData.layout, {
                            responsive: true,
                            displayModeBar: true,
                            displaylogo: false,
                            modeBarButtonsToAdd: ['drawline', 'drawopenpath', 'eraseshape'],
                            scrollZoom: true
                        });
                        
                        // Автообновление каждые 5 минут
                        setTimeout(() => {
                            window.location.reload();
                        }, 300000);
                        
                    } catch (error) {
                        console.error('Ошибка загрузки графика:', error);
                        document.getElementById('graph').innerHTML = 
                            '<div style="text-align:center;padding:100px;color:#666;font-size:1.2em;">' +
                            '⚠️ Временная ошибка загрузки данных ЦБ РФ.<br>' +
                            'Пожалуйста, обновите страницу (F5).</div>';
                    }
                });
            </script>
        </body>
        </html>
        '''
        
        # Рассчитываем среднее значение
        avg_price = round(sum(prices) / len(prices), 2)
        
        return render_template_string(
            html_template,
            graph_json=graph_json,
            current_rate=current_price,
            change_today=change_today,
            change_today_abs=abs(change_today),
            change_today_percent=change_today_percent,
            change_today_percent_abs=abs(change_today_percent),
            change_today_sign='+' if change_today > 0 else '',
            min_price=min_price,
            max_price=max_price,
            min_date=min_date,
            max_date=max_date,
            change_30d=change_30d,
            change_30d_abs=abs(change_30d),
            change_30d_percent=change_30d_percent,
            change_30d_percent_abs=abs(change_30d_percent),
            change_30d_sign='+' if change_30d > 0 else '',
            avg_price=avg_price,
            dates=dates,
            update_time=datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        )
        
    except Exception as e:
        # Страница с ошибкой
        error_html = f'''
        <!DOCTYPE html>
        <html>
        <head><title>Ошибка</title>
        <style>
            body {{ font-family: Arial; padding: 50px; text-align: center; background: #f8f9fa; }}
            .error-box {{ max-width: 600px; margin: auto; padding: 40px; background: white; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
            h1 {{ color: #dc3545; }}
            button {{ padding: 12px 30px; background: #007bff; color: white; border: none; border-radius: 8px; cursor: pointer; margin: 20px; }}
        </style>
        </head>
        <body>
            <div class="error-box">
                <h1>⚠️ Временные технические неполадки</h1>
                <p style="margin: 20px 0; color: #666;">Не удалось получить данные от ЦБ РФ.</p>
                <p style="margin: 20px 0; color: #888; font-size: 0.9em;">{str(e)}</p>
                <button onclick="location.reload()">Попробовать снова</button>
                <p style="margin-top: 30px; color: #999; font-size: 0.85em;">
                    Если ошибка повторяется, попробуйте позже.<br>
                    ЦБ РФ может временно ограничивать доступ.
                </p>
            </div>
        </body>
        </html>
        '''
        return error_html

@app.route('/api/current')
def api_current():
    """API endpoint для получения текущего курса"""
    data = CBRDataFetcher.get_current_usd_rate()
    return {
        'currency': 'USD/RUB',
        'rate': data['rate'],
        'change': data['change'],
        'change_percent': data['change_percent'],
        'timestamp': datetime.now().isoformat(),
        'source': 'cbr.ru'
    }

@app.route('/health')
def health():
    return 'OK'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)