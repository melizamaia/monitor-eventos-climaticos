import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

export interface PontoTemperatura {
  latitude: number;
  longitude: number;
  temperatura: number;
  estacao: string;
}

const API_URL = 'http://localhost:8000/temperaturas';

@Injectable({ providedIn: 'root' })
export class TemperaturasService {
  constructor(private readonly http: HttpClient) {}

  listar(): Observable<PontoTemperatura[]> {
    return this.http.get<PontoTemperatura[]>(API_URL);
  }
}
