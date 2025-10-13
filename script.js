document.addEventListener('DOMContentLoaded', function() {
    // Глобальные переменные
    let products = [];
    let currentSlide = 0;
    let slidesToShow = 3;
    const productGrid = document.getElementById('productGrid');
    const sliderDots = document.getElementById('sliderDots');
    const prevArrow = document.querySelector('.slider-arrow-prev');
    const nextArrow = document.querySelector('.slider-arrow-next');
    const cartCount = document.querySelector('.cart-count');
    const cart = JSON.parse(localStorage.getItem('cart')) || [];

    // Функция для загрузки продуктов с сервера
    async function loadProducts() {
        try {
            const response = await fetch('/api/products');
            if (response.ok) {
                products = await response.json();
                renderProducts();
                updateCartCount();
            } else {
                console.error('Ошибка загрузки продуктов:', response.status);
                // Используем fallback данные
                loadFallbackProducts();
            }
        } catch (error) {
            console.error('Ошибка сети:', error);
            loadFallbackProducts();
        }
    }

    // Fallback данные (из старого JSON)
    function loadFallbackProducts() {
        try {
            const productsData = document.getElementById('productsData');
            if (productsData) {
                const data = JSON.parse(productsData.textContent);
                products = data.products || [];
                renderProducts();
            }
        } catch (e) {
            console.error('Ошибка загрузки fallback продуктов:', e);
            products = [];
        }
    }

    // Рендеринг продуктов
    function renderProducts() {
        if (!productGrid) return;

        productGrid.innerHTML = '';
        sliderDots.innerHTML = '';

        if (products.length === 0) {
            productGrid.innerHTML = '<div class="empty-products"><p>Товары временно отсутствуют</p></div>';
            return;
        }

        const width = window.innerWidth;
        
        // Для мобильных устройств (ширина меньше 768px)
        if (width < 768) {
            // Показываем элементы слайдера для мобильной версии
            if (prevArrow) prevArrow.style.display = 'flex';
            if (nextArrow) nextArrow.style.display = 'flex';
            if (sliderDots) sliderDots.style.display = 'flex';
            
            // Устанавливаем стили для мобильного слайдера
            productGrid.style.display = 'flex';
            productGrid.style.overflowX = 'auto';
            productGrid.style.scrollSnapType = 'x mandatory';
            productGrid.style.gap = '1.5rem';
            productGrid.style.padding = '1rem 0';

            // Рассчитываем количество слайдов (1 продукт на слайд для мобильных)
            const totalSlides = products.length;
            
            // Создаем точки для навигации
            for (let i = 0; i < totalSlides; i++) {
                const dot = document.createElement('button');
                dot.className = `slider-dot ${i === 0 ? 'active' : ''}`;
                dot.addEventListener('click', () => goToSlide(i));
                sliderDots.appendChild(dot);
            }

            // Рендерим все продукты
            products.forEach((product, index) => {
                const productCard = createProductCard(product, index);
                productGrid.appendChild(productCard);
                
                setTimeout(() => {
                    productCard.classList.add('visible');
                }, index * 100);
            });

            updateSliderArrows();
            updateSliderPosition();
        } 
        // Для десктопной версии
        else {
            // Показываем элементы слайдера
            if (prevArrow) prevArrow.style.display = 'flex';
            if (nextArrow) nextArrow.style.display = 'flex';
            if (sliderDots) sliderDots.style.display = 'flex';
            
            // Устанавливаем стили для слайдера
            productGrid.style.display = 'flex';
            productGrid.style.overflowX = 'auto';
            productGrid.style.scrollSnapType = 'x mandatory';
            productGrid.style.gap = '2rem';

            // Рассчитываем количество слайдов
            const totalSlides = Math.ceil(products.length / slidesToShow);
            
            // Создаем точки для навигации
            for (let i = 0; i < totalSlides; i++) {
                const dot = document.createElement('button');
                dot.className = `slider-dot ${i === 0 ? 'active' : ''}`;
                dot.addEventListener('click', () => goToSlide(i));
                sliderDots.appendChild(dot);
            }

            // Рендерим все продукты
            products.forEach((product, index) => {
                const productCard = createProductCard(product, index);
                productGrid.appendChild(productCard);
                
                setTimeout(() => {
                    productCard.classList.add('visible');
                }, index * 100);
            });

            updateSliderArrows();
            updateSliderPosition();
        }
    }

    // Создание карточки товара
    function createProductCard(product, index) {
        const card = document.createElement('div');
        card.className = 'product-card';
        card.innerHTML = `
            <div class="card-image">
                <img src="${product.image}" alt="${product.alt || product.name}" loading="lazy">
            </div>
            <div class="card-content">
                <h3>${product.name}</h3>
                <p>${product.description}</p>
                <div class="price">${product.price.toLocaleString()} ₽/${product.unit}</div>
                <button class="add-to-cart" data-product-id="${product.id || index}">
                    <i class="fas fa-shopping-cart"></i>
                    В корзину
                </button>
            </div>
        `;

        // Обработчик добавления в корзину
        const addButton = card.querySelector('.add-to-cart');
        addButton.addEventListener('click', () => addToCart(product));

        return card;
    }

    // Добавление товара в корзину
    function addToCart(product) {
        const productId = product.id || product.name; // Используем ID или имя как идентификатор
        
        const existingItem = cart.find(item => 
            item.id === productId || item.name === product.name
        );
        
        if (existingItem) {
            existingItem.quantity += 1;
        } else {
            cart.push({
                id: productId,
                name: product.name,
                price: product.price,
                image: product.image,
                unit: product.unit,
                quantity: 1
            });
        }

        localStorage.setItem('cart', JSON.stringify(cart));
        updateCartCount();
        
        // Показываем уведомление
        showNotification(`"${product.name}" добавлен в корзину!`, 'success');
    }

    // Обновление счетчика корзины
    function updateCartCount() {
        if (cartCount) {
            const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
            cartCount.textContent = totalItems;
            
            // Обновляем все счетчики на странице
            document.querySelectorAll('.cart-count').forEach(el => {
                el.textContent = totalItems;
            });
        }
    }

    // Функции слайдера
    function updateSliderArrows() {
        if (prevArrow && nextArrow) {
            const width = window.innerWidth;
            
            if (width < 768) {
                // Для мобильных: 1 продукт на слайд
                prevArrow.style.display = currentSlide === 0 ? 'none' : 'flex';
                nextArrow.style.display = currentSlide >= products.length - 1 ? 'none' : 'flex';
            } else {
                // Для десктопа: несколько продуктов на слайд
                const totalSlides = Math.ceil(products.length / slidesToShow);
                prevArrow.style.display = currentSlide === 0 ? 'none' : 'flex';
                nextArrow.style.display = currentSlide >= totalSlides - 1 ? 'none' : 'flex';
            }
        }
    }

    function updateSliderPosition() {
        if (!productGrid || products.length === 0) return;
        
        const width = window.innerWidth;
        const card = productGrid.querySelector('.product-card');
        if (!card) return;
        
        if (width < 768) {
            // Для мобильных: прокрутка по одному продукту
            const cardWidth = card.offsetWidth;
            const gap = 24; // 1.5rem в пикселях
            const scrollAmount = (cardWidth + gap) * currentSlide;
            
            productGrid.scrollTo({
                left: scrollAmount,
                behavior: 'smooth'
            });
        } else {
            // Для десктопа: прокрутка по несколько продуктов
            const cardWidth = card.offsetWidth;
            const gap = 32; // 2rem в пикселях
            const scrollAmount = (cardWidth + gap) * slidesToShow * currentSlide;
            
            productGrid.scrollTo({
                left: scrollAmount,
                behavior: 'smooth'
            });
        }

        // Обновляем активную точку
        document.querySelectorAll('.slider-dot').forEach((dot, index) => {
            dot.classList.toggle('active', index === currentSlide);
        });

        updateSliderArrows();
    }

    function goToSlide(slideIndex) {
        const width = window.innerWidth;
        
        if (width < 768) {
            // Для мобильных: 1 продукт на слайд
            currentSlide = Math.max(0, Math.min(slideIndex, products.length - 1));
        } else {
            // Для десктопа: несколько продуктов на слайд
            const totalSlides = Math.ceil(products.length / slidesToShow);
            currentSlide = Math.max(0, Math.min(slideIndex, totalSlides - 1));
        }
        
        updateSliderPosition();
    }

    // Обработчики стрелок слайдера
    if (prevArrow) {
        prevArrow.addEventListener('click', () => {
            goToSlide(currentSlide - 1);
        });
    }

    if (nextArrow) {
        nextArrow.addEventListener('click', () => {
            const width = window.innerWidth;
            
            if (width < 768) {
                goToSlide(currentSlide + 1);
            } else {
                goToSlide(currentSlide + 1);
            }
        });
    }

    // Обработчик свайпа для мобильных устройств
    let touchStartX = 0;
    let touchEndX = 0;

    if (productGrid) {
        productGrid.addEventListener('touchstart', (e) => {
            touchStartX = e.changedTouches[0].screenX;
        });

        productGrid.addEventListener('touchend', (e) => {
            touchEndX = e.changedTouches[0].screenX;
            handleSwipe();
        });
    }

    function handleSwipe() {
        const minSwipeDistance = 50; // Минимальное расстояние свайпа
        
        if (touchStartX - touchEndX > minSwipeDistance) {
            // Свайп влево - следующий слайд
            goToSlide(currentSlide + 1);
        } 
        
        if (touchEndX - touchStartX > minSwipeDistance) {
            // Свайп вправо - предыдущий слайд
            goToSlide(currentSlide - 1);
        }
    }

    // Автоматическое определение количества отображаемых слайдов
    function updateSlidesToShow() {
        const width = window.innerWidth;
        if (width < 768) {
            // На мобильных показываем по 1 продукту
            slidesToShow = 1;
        } else if (width < 1024) {
            slidesToShow = 2;
        } else {
            slidesToShow = 3;
        }
        
        // Перерисовываем продукты при изменении размера
        if (products.length > 0) {
            renderProducts();
            goToSlide(0);
        }
    }

    // Обработчик изменения размера окна
    window.addEventListener('resize', updateSlidesToShow);

    // Функция для показа уведомлений
    function showNotification(message, type = 'success') {
        // Удаляем существующие уведомления
        document.querySelectorAll('.notification').forEach(el => el.remove());

        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i>
            <span>${message}</span>
            <button onclick="this.parentElement.remove()">&times;</button>
        `;

        document.body.appendChild(notification);

        // Автоматическое удаление через 3 секунды
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 3000);
    }

    // Инициализация мобильного меню
    const mobileMenuToggle = document.getElementById('mobileMenuToggle');
    const mainNav = document.getElementById('mainNav');
    const navLinks = document.querySelectorAll('.nav-link');
    const body = document.body;

    if (mobileMenuToggle && mainNav) {
        function toggleMenu() {
            mobileMenuToggle.classList.toggle('active');
            mainNav.classList.toggle('active');
            body.classList.toggle('menu-open');
            body.style.overflow = body.classList.contains('menu-open') ? 'hidden' : '';
        }

        mobileMenuToggle.addEventListener('click', toggleMenu);
        navLinks.forEach(link => link.addEventListener('click', () => {
            if (mainNav.classList.contains('active')) toggleMenu();
        }));
    }

    // Плавная прокрутка для якорных ссылок
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;

            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Анимация появления элементов при скролле
    function animateOnScroll() {
        const elements = document.querySelectorAll('.product-card, .hero-content, .advantage-card');
        
        elements.forEach(element => {
            const elementTop = element.getBoundingClientRect().top;
            const elementVisible = 150;
            
            if (elementTop < window.innerHeight - elementVisible) {
                element.classList.add('visible');
            }
        });
    }

    // Инициализация
    window.addEventListener('scroll', animateOnScroll);
    window.addEventListener('load', animateOnScroll);

    // Загружаем продукты и инициализируем
    updateSlidesToShow();
    loadProducts();
    updateCartCount();

    // Периодическое обновление продуктов (каждые 5 минут)
    setInterval(loadProducts, 5 * 60 * 1000);

    // Добавляем глобальную функцию для уведомлений
    window.showNotification = showNotification;
});
