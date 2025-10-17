document.addEventListener('DOMContentLoaded', function() {
    // Helper function to parse JSON from script tags
    function parseJsonFromScript(id) {
        const scriptTag = document.getElementById(id);
        if (scriptTag) {
            try {
                return JSON.parse(scriptTag.textContent);
            } catch (e) {
                console.error(`Error parsing JSON from script ID "${id}":`, e);
                return null;
            }
        }
        return null;
    }

    // Store chart instances globally (or in a scope accessible by a cleanup function)
    let registrationChartInstance = null;
    let roleChartInstance = null;
    let prefLangChartInstance = null;
    let lessonLangChartInstance = null;

    // Function to destroy existing charts
    function destroyCharts() {
        if (registrationChartInstance) {
            registrationChartInstance.destroy();
            registrationChartInstance = null;
        }
        if (roleChartInstance) {
            roleChartInstance.destroy();
            roleChartInstance = null;
        }
        if (prefLangChartInstance) {
            prefLangChartInstance.destroy();
            prefLangChartInstance = null;
        }
        if (lessonLangChartInstance) {
            lessonLangChartInstance.destroy();
            lessonLangChartInstance = null;
        }
    }

    // Call destroyCharts when the DOM content is loaded (in case of reloads/navigating back)
    // This is crucial for environments where the DOM might not be fully torn down
    // or if this script might execute multiple times.
    destroyCharts();

    // Chart.js global configuration
    Chart.defaults.font.family = "'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = '#6c757d';
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.padding = 20;

    // Helper function to calculate proper y-axis max value
    function calculateYAxisMax(data, minMax = 10, stepSize = 1) {
        if (!data || data.length === 0) return minMax;
        
        const maxValue = Math.max(...data);
        if (maxValue <= 0) return minMax;
        
        // Calculate a reasonable max value that's slightly above the actual max
        const roundedMax = Math.ceil(maxValue * 1.2);
        
        // Ensure it's at least the minimum max value
        return Math.max(roundedMax, minMax);
    }

    // Helper function to calculate step size based on max value
    function calculateStepSize(maxValue) {
        if (maxValue <= 10) return 1;
        if (maxValue <= 50) return 5;
        if (maxValue <= 100) return 10;
        if (maxValue <= 500) return 50;
        if (maxValue <= 1000) return 100;
        return Math.ceil(maxValue / 10);
    }

    // --- User Registration Trend Chart ---
    const regLabels = parseJsonFromScript('reg_chart_labels');
    const regData = parseJsonFromScript('reg_chart_data');
    if (regLabels && regData) {
        const regCtx = document.getElementById('registrationChart').getContext('2d');
        const regMaxValue = calculateYAxisMax(regData, 5);
        const regStepSize = calculateStepSize(regMaxValue);
        
        registrationChartInstance = new Chart(regCtx, {
            type: 'line',
            data: {
                labels: regLabels,
                datasets: [{
                    label: 'New Users',
                    data: regData,
                    borderColor: 'rgba(102, 126, 234, 1)',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: true,
                    pointBackgroundColor: 'rgba(102, 126, 234, 1)',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    pointRadius: 6,
                    pointHoverRadius: 8,
                    pointHoverBackgroundColor: 'rgba(102, 126, 234, 1)',
                    pointHoverBorderColor: '#ffffff',
                    pointHoverBorderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        borderColor: 'rgba(102, 126, 234, 0.5)',
                        borderWidth: 1,
                        cornerRadius: 8,
                        displayColors: false,
                        callbacks: {
                            title: function(context) {
                                return '📅 ' + context[0].label;
                            },
                            label: function(context) {
                                return '👥 ' + context.parsed.y + ' new users';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45
                        }
                    },
                    y: {
                        beginAtZero: true,
                        max: regMaxValue,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)',
                            drawBorder: false
                        },
                        ticks: {
                            stepSize: regStepSize,
                            callback: function(value) {
                                return value + ' users';
                            }
                        }
                    }
                },
                animation: {
                    duration: 2000,
                    easing: 'easeInOutQuart'
                }
            }
        });
    }

    // --- User Role Distribution Chart ---
    const roleLabels = parseJsonFromScript('role_labels');
    const roleData = parseJsonFromScript('role_data');
    if (roleLabels && roleData) {
        const roleCtx = document.getElementById('roleChart').getContext('2d');
        roleChartInstance = new Chart(roleCtx, {
            type: 'doughnut',
            data: {
                labels: roleLabels,
                datasets: [{
                    data: roleData,
                    backgroundColor: [
                        'rgba(102, 126, 234, 0.8)',
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(255, 206, 86, 0.8)',
                        'rgba(75, 192, 192, 0.8)',
                    ],
                    borderColor: [
                        'rgba(102, 126, 234, 1)',
                        'rgba(255, 99, 132, 1)',
                        'rgba(255, 206, 86, 1)',
                        'rgba(75, 192, 192, 1)',
                    ],
                    borderWidth: 2,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '60%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true,
                            pointStyle: 'circle'
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        borderColor: 'rgba(102, 126, 234, 0.5)',
                        borderWidth: 1,
                        cornerRadius: 8,
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed / total) * 100).toFixed(1);
                                return context.label + ': ' + context.parsed + ' (' + percentage + '%)';
                            }
                        }
                    }
                },
                animation: {
                    animateRotate: true,
                    animateScale: true,
                    duration: 2000,
                    easing: 'easeInOutQuart'
                }
            }
        });
    }

    // --- Preferred Language Chart ---
    const prefLangLabels = parseJsonFromScript('pref_lang_labels');
    const prefLangData = parseJsonFromScript('pref_lang_data');
    if (prefLangLabels && prefLangData) {
        const prefLangCtx = document.getElementById('prefLangChart').getContext('2d');
        const prefLangMaxValue = calculateYAxisMax(prefLangData, 5);
        const prefLangStepSize = calculateStepSize(prefLangMaxValue);
        
        prefLangChartInstance = new Chart(prefLangCtx, {
            type: 'bar',
            data: {
                labels: prefLangLabels,
                datasets: [{
                    label: 'Number of Users',
                    data: prefLangData,
                    backgroundColor: [
                        'rgba(102, 126, 234, 0.8)',
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(255, 206, 86, 0.8)',
                        'rgba(75, 192, 192, 0.8)',
                    ],
                    borderColor: [
                        'rgba(102, 126, 234, 1)',
                        'rgba(255, 99, 132, 1)',
                        'rgba(255, 206, 86, 1)',
                        'rgba(75, 192, 192, 1)',
                    ],
                    borderWidth: 2,
                    borderRadius: 8,
                    borderSkipped: false,
                    hoverBackgroundColor: [
                        'rgba(102, 126, 234, 1)',
                        'rgba(255, 99, 132, 1)',
                        'rgba(255, 206, 86, 1)',
                        'rgba(75, 192, 192, 1)',
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        borderColor: 'rgba(102, 126, 234, 0.5)',
                        borderWidth: 1,
                        cornerRadius: 8,
                        displayColors: false,
                        callbacks: {
                            title: function(context) {
                                return '🌍 ' + context[0].label;
                            },
                            label: function(context) {
                                return '👥 ' + context.parsed.y + ' users';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        beginAtZero: true,
                        max: prefLangMaxValue,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)',
                            drawBorder: false
                        },
                        ticks: {
                            stepSize: prefLangStepSize,
                            callback: function(value) {
                                return value + ' users';
                            }
                        }
                    }
                },
                animation: {
                    duration: 2000,
                    easing: 'easeInOutQuart'
                }
            }
        });
    }

    // --- Lesson Language (Average Highest Unlocked Levels) Chart ---
    const lessonLangLabels = parseJsonFromScript('lesson_lang_labels');
    const lessonLangData = parseJsonFromScript('lesson_lang_data');

    if (lessonLangLabels && lessonLangData) {
        const lessonLangCtx = document.getElementById('lessonLangChart').getContext('2d');
        
        // For learning progress, we know the maximum level is 100
        const maxLevel = 100;
        const lessonLangMaxValue = Math.max(maxLevel, calculateYAxisMax(lessonLangData, 10));
        const lessonLangStepSize = calculateStepSize(lessonLangMaxValue);
        
        lessonLangChartInstance = new Chart(lessonLangCtx, {
            type: 'bar',
            data: {
                labels: lessonLangLabels,
                datasets: [{
                    label: 'Average Highest Unlocked Level',
                    data: lessonLangData,
                    backgroundColor: [
                        'rgba(255, 159, 64, 0.8)',
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(75, 192, 192, 0.8)',
                        'rgba(153, 102, 255, 0.8)',
                    ],
                    borderColor: [
                        'rgba(255, 159, 64, 1)',
                        'rgba(54, 162, 235, 1)',
                        'rgba(75, 192, 192, 1)',
                        'rgba(153, 102, 255, 1)',
                    ],
                    borderWidth: 2,
                    borderRadius: 8,
                    borderSkipped: false,
                    hoverBackgroundColor: [
                        'rgba(255, 159, 64, 1)',
                        'rgba(54, 162, 235, 1)',
                        'rgba(75, 192, 192, 1)',
                        'rgba(153, 102, 255, 1)',
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        borderColor: 'rgba(255, 159, 64, 0.5)',
                        borderWidth: 1,
                        cornerRadius: 8,
                        displayColors: false,
                        callbacks: {
                            title: function(context) {
                                return '📚 ' + context[0].label;
                            },
                            label: function(context) {
                                return '📈 Average Level: ' + parseFloat(context.raw).toFixed(2);
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        beginAtZero: true,
                        max: lessonLangMaxValue,
                        title: {
                            display: true,
                            text: 'Average Level',
                            color: '#6c757d',
                            font: {
                                size: 12,
                                weight: 'bold'
                            }
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)',
                            drawBorder: false
                        },
                        ticks: {
                            stepSize: lessonLangStepSize,
                            callback: function(value) {
                                return 'Level ' + value;
                            }
                        }
                    }
                },
                animation: {
                    duration: 2000,
                    easing: 'easeInOutQuart'
                }
            }
        });
    }

    // Add smooth animations to metric cards
    const metricCards = document.querySelectorAll('.card');
    metricCards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            card.style.transition = 'all 0.6s ease-out';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });

    // Add hover effects to activity items
    const activityItems = document.querySelectorAll('.activity-item');
    activityItems.forEach(item => {
        item.addEventListener('mouseenter', function() {
            this.style.transform = 'translateX(5px)';
            this.style.transition = 'transform 0.2s ease';
        });
        
        item.addEventListener('mouseleave', function() {
            this.style.transform = 'translateX(0)';
        });
    });
});