import { NestFactory } from '@nestjs/core';
import { FastifyAdapter, NestFastifyApplication } from '@nestjs/platform-fastify';
import { AppModule } from './app.module';
import { ValidationPipe } from '@nestjs/common';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';

async function bootstrap() {
  const app = await NestFactory.create<NestFastifyApplication>(
    AppModule,
    new FastifyAdapter(),
  );

  // Global Validation
  app.useGlobalPipes(new ValidationPipe({ transform: true }));

  // Swagger Configuration
  const config = new DocumentBuilder()
    .setTitle('NestJS Fastify Boilerplate 2026')
    .setVersion('1.0')
    .build();
  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('docs', app, document);

  // Listen on all interfaces
  await app.listen(process.env.PORT ?? 3000, '0.0.0.0');
}
bootstrap();
