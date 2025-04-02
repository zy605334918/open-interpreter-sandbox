document.addEventListener('DOMContentLoaded', function() {
    // Initialize charts
    const cpuCtx = document.getElementById('cpuChart').getContext('2d');
    const memoryCtx = document.getElementById('memoryChart').getContext('2d');
    
    const cpuChart = new Chart(cpuCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'CPU Usage %',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1,
                fill: false
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });
    
    const memoryChart = new Chart(memoryCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Memory Usage %',
                data: [],
                borderColor: 'rgb(54, 162, 235)',
                tension: 0.1,
                fill: false
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });
    
    // Update stats every second
    function updateStats() {
        fetch('/api/stats')
            .then(response => response.json())
            .then(data => {
                // Update current stats
                document.getElementById('cpu-usage').textContent = data.cpu;
                document.getElementById('memory-usage').textContent = data.memory_used;
                document.getElementById('memory-total').textContent = data.memory_total;
                document.getElementById('memory-percent').textContent = data.memory;
                
                // Update charts
                if (cpuChart.data.labels.length > 15) {
                    cpuChart.data.labels.shift();
                    cpuChart.data.datasets[0].data.shift();
                    
                    memoryChart.data.labels.shift();
                    memoryChart.data.datasets[0].data.shift();
                }
                
                cpuChart.data.labels.push(data.timestamp);
                cpuChart.data.datasets[0].data.push(data.cpu);
                cpuChart.update();
                
                memoryChart.data.labels.push(data.timestamp);
                memoryChart.data.datasets[0].data.push(data.memory);
                memoryChart.update();
                
                // Update security events
                const eventsList = document.getElementById('events-list');
                eventsList.innerHTML = '';
                
                data.security_events.forEach(event => {
                    const eventElement = document.createElement('div');
                    eventElement.className = 'event-item';
                    eventElement.innerHTML = `
                        <div class="event-timestamp">${event.timestamp}</div>
                        <div class="event-message">${event.message}</div>
                    `;
                    eventsList.prepend(eventElement);
                });
            });
    }
    
    // Initial update
    updateStats();
    
    // Update every second
    setInterval(updateStats, 1000);
});